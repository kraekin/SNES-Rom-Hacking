# SNES Rom Hacking
 Various SNES Rom hacking things. Research, Scripts, etc. 


 Currently working on E.V.O Search for Eden.
  - basic graphics decompression script working with the help of AI. it seems to decompress the graphics just fine, but im sure it still needs work. Havent dealt with recompression just yet as some early tests were unsuccessful. Will come back to that soon. 

  Usage: python decomptest.py <offset> [rom_file] [--special]
  Offset can be decimal or hex (with 0x prefix) 
  Default ROM file is 'evo.sfc' if not specified
  Add --special to force special mode decompression
  
  
