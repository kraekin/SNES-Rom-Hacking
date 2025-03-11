import os
import sys

def decompress_evo_data(compressed_data, start_offset=0, special_mode=False):
    """
    Decompress E.V.O.: Search for Eden compressed data

    Args:
        compressed_data: Bytes object containing compressed data
        start_offset: Starting offset in the compressed data
        special_mode: Whether to use special mode decompression (jump target 5)

    Returns:
        Bytes object containing decompressed data
    """
    output = bytearray()
    pos = start_offset

    # Read first control byte
    ec_value = compressed_data[pos]
    pos += 1

    # Check for special flag in control byte
    special_flag = False
    if ec_value & 0x80:
        ec_value &= 0x7F
        special_flag = True

    # Read data size (16-bit)
    data_size = compressed_data[pos] + (compressed_data[pos+1] << 8)
    pos += 2

    print(f"Control byte: {ec_value:02X}")
    print(f"Special flag: {special_flag}")
    print(f"Data size: {data_size} bytes")
    
    # Special mode uses a counter initially set to 0x0100
    # This is tracked in $EE in the assembly
    special_counter = 0x100 if special_mode else None
    
    bit_count = 8
    command_byte = 0

    # Main decompression loop
    while len(output) < data_size and pos < len(compressed_data):
        # Check special mode counter
        if special_mode and special_counter <= 0:
            print(f"Special mode counter reached 0, terminating early at {len(output)} bytes")
            break
            
        # Get next command bit
        if bit_count == 8:
            bit_count = 0
            command_byte = compressed_data[pos]
            pos += 1

        bit_count += 1
        command_bit = command_byte & 1
        command_byte >>= 1

        if command_bit:
            # Copy literal byte
            if pos >= len(compressed_data):
                print(f"Error: Reached end of input data at position {pos}")
                break

            output.append(compressed_data[pos])
            pos += 1
            
            # Decrement special counter if in special mode
            if special_mode:
                special_counter -= 1
        else:
            # Read match info (16-bit)
            if pos + 1 >= len(compressed_data):
                print(f"Error: Not enough data for match info at position {pos}")
                break

            match_info = compressed_data[pos] + (compressed_data[pos+1] << 8)
            pos += 2

            # Extract offset and length
            offset = (match_info & 0x0FFF) + 1
            length_field = (match_info >> 12) & 0x0F

            # Calculate total length
            copy_length = length_field + ec_value

            # Handle extended length
            if length_field == 0x0F and special_flag:
                if pos >= len(compressed_data):
                    print(f"Error: Not enough data for extended length at position {pos}")
                    break

                extra_length = compressed_data[pos]
                pos += 1
                copy_length += extra_length

            # Error checks
            if offset > len(output):
                print(f"Error: Invalid offset {offset} at position {pos-2} (output size: {len(output)})")
                # Try to recover by skipping this command
                continue
                
            if copy_length > 0x2000:  # Reasonable upper limit for copy length
                print(f"Warning: Suspiciously large copy_length: {copy_length}, limiting to 0x2000")
                copy_length = 0x2000
                
            # Check if copy would exceed data_size
            if len(output) + copy_length > data_size:
                print(f"Warning: Copy would exceed expected data size. Limiting copy.")
                copy_length = data_size - len(output)

            # Ensure we have valid output bytes to copy from
            if len(output) == 0:
                print(f"Error: Cannot copy from empty output buffer")
                break

            # Copy bytes from earlier in the output
            for i in range(copy_length):
                output.append(output[len(output) - offset])
                
            # Decrement special counter if in special mode
            if special_mode:
                special_counter -= 1

    # Check if we fully decompressed as expected
    if len(output) < data_size:
        print(f"Warning: Incomplete decompression. Expected {data_size} bytes, got {len(output)} bytes.")
    
    return output

def detect_decompress_parameters(compressed_data, start_offset=0):
    """
    Try to auto-detect if this is standard mode or special mode compression
    
    Args:
        compressed_data: Bytes object containing compressed data
        start_offset: Starting offset in the compressed data
        
    Returns:
        A tuple of (is_special_mode, control_byte, data_size)
    """
    if start_offset + 3 >= len(compressed_data):
        return False, 0, 0
        
    # Read control byte and check its high bit
    control_byte = compressed_data[start_offset]
    special_flag = (control_byte & 0x80) > 0
    
    # Read data size
    data_size = compressed_data[start_offset+1] + (compressed_data[start_offset+2] << 8)
    
    # Heuristic: special mode often has a specific pattern
    # If control byte is 0x01 and data_size is divisible by 0x100, it's likely special mode
    is_special_mode = control_byte == 0x01 and data_size % 0x100 == 0
    
    # Alternatively, if the compressed data contains a sequence common in special mode
    # Look ahead for signature bytes if possible
    if start_offset + 20 < len(compressed_data):
        # Look for patterns specific to special mode
        # (These would need to be adjusted based on actual analysis)
        pass
    
    return is_special_mode, control_byte, data_size

def dump_hex(data, bytes_per_line=16):
    """
    Return a nicely formatted hex dump of the data
    """
    result = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i:i+bytes_per_line]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        result.append(f"{i:08X}:  {hex_part:<{bytes_per_line*3}}  {ascii_part}")
    return "\n".join(result)

def main():
    # Check if offset is provided as command-line argument
    if len(sys.argv) < 2:
        print("Usage: python script.py <offset> [rom_file] [--special]")
        print("Offset can be decimal or hex (with 0x prefix)")
        print("Default ROM file is 'evo.sfc' if not specified")
        print("Add --special to force special mode decompression")
        sys.exit(1)

    # Parse the offset
    try:
        offset_str = sys.argv[1]
        if offset_str.startswith('0x') or offset_str.startswith('0X'):
            decompression_offset = int(offset_str, 16)
        else:
            decompression_offset = int(offset_str)
    except ValueError:
        print("Error: Invalid offset value. Please provide a valid decimal or hex number.")
        sys.exit(1)

    # Get ROM file from argument or use default
    rom_file = "evo.sfc"
    special_mode = False
    
    # Process remaining arguments
    for arg in sys.argv[2:]:
        if arg == "--special":
            special_mode = True
        elif not arg.startswith("--"):
            rom_file = arg

    # Check if the ROM file exists
    if not os.path.exists(rom_file):
        print(f"Error: ROM file '{rom_file}' not found.")
        sys.exit(1)

    # Load the ROM file
    try:
        with open(rom_file, "rb") as f:
            rom_data = f.read()
    except Exception as e:
        print(f"Error loading ROM file: {e}")
        sys.exit(1)

    # Make sure the offset is valid
    if decompression_offset >= len(rom_data):
        print(f"Error: Offset 0x{decompression_offset:X} is beyond the size of the ROM ({len(rom_data)} bytes).")
        sys.exit(1)

    print(f"ROM size: {len(rom_data)} bytes")
    print(f"Attempting to decompress data at offset: 0x{decompression_offset:X}")

    # Auto-detect parameters if not forced
    if not special_mode:
        detected_special, control_byte, data_size = detect_decompress_parameters(rom_data, decompression_offset)
        if detected_special:
            print(f"Auto-detected special mode compression!")
            special_mode = True
    
    print(f"Using {'special' if special_mode else 'standard'} mode decompression")

    # Decompress the data
    try:
        decompressed_data = decompress_evo_data(rom_data, decompression_offset, special_mode)

        # Write the decompressed data to a file (using offset and mode in filename)
        mode_str = "_special" if special_mode else ""
        output_file = f"{decompression_offset:x}{mode_str}.bin"
        with open(output_file, "wb") as f:
            f.write(decompressed_data)

        print(f"\nSuccessfully decompressed {len(decompressed_data)} bytes.")
        print(f"Decompressed data saved to: {output_file}")

        # Print a hex dump of the first 128 bytes (or less) of decompressed data
        print("\nFirst 128 bytes of decompressed data:")
        print(dump_hex(decompressed_data[:128]))

    except Exception as e:
        print(f"Error during decompression: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
