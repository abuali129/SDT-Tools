import sys
import os
import struct
import csv
from colorama import Fore, init

init()  # Initialize colorama

# Language ID mapping
LANG_MAP = {
    1: "[ENG]",
    2: "[FRE]",
    3: "[GER]",
    4: "[ITA]",
    5: "[SPA]",
    7: "[JPN]"
}

def looks_like_entry_header(data):
    """
    Simple heuristic to detect if a 16-byte block is likely a valid entry header.
    Returns True if it seems valid, False otherwise.
    """
    if len(data) < 16:
        return False

    # Example heuristics:
    # - Start time and end time should be reasonable numbers
    # - Lang ID should be within known range or small value
    start_time = struct.unpack('<I', data[0:4])[0]
    end_time = struct.unpack('<I', data[4:8])[0]
    lang_id = struct.unpack('<H', data[14:16])[0]

    # Basic sanity checks
    if start_time > 0xFFFFFFFF or end_time > 0xFFFFFFFF:
        return False
    if lang_id not in LANG_MAP and not (1 <= lang_id <= 20):
        return False

    return True

def parse_pacb_file(file_path, output_csv):
    PACB_SIGNATURE = b'PACB'

    with open(file_path, 'rb') as f:
        data = f.read()

        # Search for 'PACB' signature
        pacb_offset = data.find(PACB_SIGNATURE)
        if pacb_offset == -1:
            print(f"{Fore.RED}Error: 'PACB' signature not found in the file.{Fore.RESET}")
            return

        print(f"'PACB' signature found at offset: 0x{pacb_offset:X}")

        # Read text block size (4 bytes after PACB) — assuming little-endian
        text_block_size_bytes = data[pacb_offset + 4 : pacb_offset + 8]
        if len(text_block_size_bytes) < 4:
            print("Error: Unable to read text block size.")
            return

        text_block_size = int.from_bytes(text_block_size_bytes, byteorder='little')
        print(f"Text Block Size: 0x{text_block_size:X}")

        # Start reading text block at PACB + 8
        text_start_offset = pacb_offset + 8
        current_pos = text_start_offset
        entries = []

        while current_pos < text_start_offset + text_block_size:
            if current_pos + 16 > len(data):
                print(f"{Fore.RED}Error: Unexpected end of file.{Fore.RESET}")
                break

            entry_data = data[current_pos:current_pos + 16]

            if len(entry_data) < 16:
                break  # Incomplete entry

            # Safety check: is this really an entry header?
            if not looks_like_entry_header(entry_data):
                print(f"{Fore.YELLOW}Warning: Invalid entry header detected at offset 0x{current_pos:X}, stopping parsing.{Fore.RESET}")
                break

            try:
                start_time = struct.unpack('<I', entry_data[0:4])[0]
                end_time = struct.unpack('<I', entry_data[4:8])[0]
                unknown = struct.unpack('<I', entry_data[8:12])[0]  # Keep for later use
                entry_size_lang = struct.unpack('<H', entry_data[12:14])[0]  # Keep for later use
                lang_id = struct.unpack('<H', entry_data[14:16])[0]
            except Exception as e:
                print(f"{Fore.RED}Error unpacking entry at 0x{current_pos:X}: {e}{Fore.RESET}")
                break

            # Map Lang ID to readable format
            lang_label = LANG_MAP.get(lang_id, f"[{lang_id}]")

            # Find null-terminated string starting at current_pos + 16
            text_end = data.find(b'\x00', current_pos + 16)
            if text_end == -1 or text_end - (current_pos + 16) < 0:
                print(f"{Fore.RED}Warning: Missing null terminator for text at offset 0x{current_pos:X}.{Fore.RESET}")
                text = ''
                next_entry = current_pos + entry_size_lang
            else:
                text_bytes = data[current_pos + 16:text_end]
                try:
                    text = text_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    text = text_bytes.decode('utf-8', errors='replace')
                next_entry = current_pos + entry_size_lang

            # Save only needed fields to CSV
            entries.append([
                start_time,
                end_time,
                lang_label,
                text
            ])

            current_pos = next_entry

        # Write to explicitly provided CSV path
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                "Start Time", "End Time", "Lang ID", "Text"
            ])
            writer.writerows(entries)

        print(f"{Fore.CYAN}Parsed {len(entries)} entries. Saved to '{output_csv}'.{Fore.RESET}")

# Entry point for drag-and-drop or command line
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"{Fore.YELLOW}Usage: Tool.py <input_file.sdt> <output_file.csv>{Fore.RESET}")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    print(f"Processing file: {input_file}")
    parse_pacb_file(input_file, output_file)