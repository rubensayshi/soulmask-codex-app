"""
Read the Soulmask pak file index and list/extract specific texture assets.
Supports UE4 pak format version 8/11 with AES-256 encryption.
"""
import struct
import hashlib
from Crypto.Cipher import AES
import os, sys, zlib, io

PAK = r"E:\SteamLibrary\steamapps\common\Soulmask\WS\Content\Paks\WS-WindowsNoEditor.pak"
AES_KEY = bytes.fromhex("C54DB0B49CCC34DE99DF9A0B9E60073F4C88D9A122AA9B2A5E1E7667E7BBA995")

PAK_MAGIC = 0x5A6F12E1


def aes_decrypt(data: bytes, key: bytes) -> bytes:
    # Pad to 16-byte boundary
    pad = (16 - len(data) % 16) % 16
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.decrypt(data + b'\x00' * pad)[:len(data)]


def read_string(buf: bytes, offset: int):
    length = struct.unpack_from('<i', buf, offset)[0]
    offset += 4
    if length == 0:
        return '', offset
    if length < 0:
        # UTF-16
        size = -length * 2
        s = buf[offset:offset + size - 2].decode('utf-16-le')
        return s, offset + size
    else:
        s = buf[offset:offset + length - 1].decode('utf-8', errors='replace')
        return s, offset + length


def main():
    filter_pattern = sys.argv[1].lower() if len(sys.argv) > 1 else ''
    extract_to = sys.argv[2] if len(sys.argv) > 2 else None

    with open(PAK, 'rb') as f:
        # Read footer — last 226 bytes for v11, try from end
        f.seek(-226, 2)
        footer = f.read(226)

        # Find magic in footer
        magic_pos = None
        for i in range(len(footer) - 4, -1, -1):
            if struct.unpack_from('<I', footer, i)[0] == PAK_MAGIC:
                magic_pos = i
                break

        if magic_pos is None:
            print("Magic not found in footer!")
            return

        footer = footer[magic_pos:]
        magic, version = struct.unpack_from('<II', footer, 0)
        print(f"PAK magic: 0x{magic:08X}, version: {version}")

        if version >= 8:
            # v8+: magic(4) + version(4) + index_offset(8) + index_size(8) + sha1(20) + encrypted(1) + encrypted_sha1(20) + compression_name_count(4) + ...
            index_offset = struct.unpack_from('<q', footer, 8)[0]
            index_size = struct.unpack_from('<q', footer, 16)[0]
            encrypted = footer[44]
            print(f"Index offset: {index_offset}, size: {index_size}, encrypted: {encrypted}")
        else:
            index_offset = struct.unpack_from('<q', footer, 8)[0]
            index_size = struct.unpack_from('<q', footer, 16)[0]
            encrypted = 0

        # Read index
        f.seek(index_offset)
        index_data = f.read(index_size)

        if encrypted:
            index_data = aes_decrypt(index_data, AES_KEY)

        # Parse index
        offset = 0
        mount_point, offset = read_string(index_data, offset)
        print(f"Mount point: {mount_point}")

        entry_count = struct.unpack_from('<i', index_data, offset)[0]
        offset += 4
        print(f"Entry count: {entry_count}")

        entries = []
        for _ in range(entry_count):
            filename, offset = read_string(index_data, offset)
            # Entry: offset(8) + size(8) + uncompressed_size(8) + compression_method(4) + timestamp(8, v1 only) + sha1(20) + blocks...
            if version < 3:
                file_offset = struct.unpack_from('<q', index_data, offset)[0]; offset += 8
                file_size = struct.unpack_from('<q', index_data, offset)[0]; offset += 8
                uncompressed = struct.unpack_from('<q', index_data, offset)[0]; offset += 8
                compression = struct.unpack_from('<I', index_data, offset)[0]; offset += 4
                offset += 8  # timestamp
            elif version < 8:
                file_offset = struct.unpack_from('<q', index_data, offset)[0]; offset += 8
                file_size = struct.unpack_from('<q', index_data, offset)[0]; offset += 8
                uncompressed = struct.unpack_from('<q', index_data, offset)[0]; offset += 8
                compression = struct.unpack_from('<I', index_data, offset)[0]; offset += 4
                offset += 20  # sha1
                if compression != 0:
                    block_count = struct.unpack_from('<i', index_data, offset)[0]; offset += 4
                    offset += block_count * 16
                offset += 1  # encrypted flag
                offset += 4  # block size
            else:
                file_offset = struct.unpack_from('<q', index_data, offset)[0]; offset += 8
                file_size = struct.unpack_from('<q', index_data, offset)[0]; offset += 8
                uncompressed = struct.unpack_from('<q', index_data, offset)[0]; offset += 8
                compression = struct.unpack_from('<I', index_data, offset)[0]; offset += 4
                offset += 20  # sha1
                if compression != 0:
                    block_count = struct.unpack_from('<i', index_data, offset)[0]; offset += 4
                    offset += block_count * 16
                encrypted_flag = index_data[offset]; offset += 1
                block_size = struct.unpack_from('<I', index_data, offset)[0]; offset += 4

            entries.append((filename, file_offset, file_size, uncompressed, compression))

        # Filter and print
        matches = [(fn, fo, fs, us, cm) for fn, fo, fs, us, cm in entries
                   if filter_pattern in fn.lower()]

        if filter_pattern:
            print(f"\nMatches for '{filter_pattern}': {len(matches)}")
            for fn, fo, fs, us, cm in matches[:100]:
                print(f"  {fn}  [{fs} bytes]")
        else:
            print(f"\nAll {len(entries)} entries (showing UI-related):")
            for fn, fo, fs, us, cm in entries:
                if 'UI' in fn or 'ui' in fn:
                    print(f"  {fn}  [{fs} bytes]")

        print(f"\nTotal entries listed.")


if __name__ == '__main__':
    main()
