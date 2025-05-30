import os
import csv
import struct
import sys
import tempfile
from colorama import Fore, init

init()

# Language mapping
LANG_MAP = {
    "[ENG]": 1,
    "[FRE]": 2,
    "[GER]": 3,
    "[ITA]": 4,
    "[SPA]": 5,
    "[JPN]": 7
}

def lang_label_to_id(label):
    label = label.strip()
    if label in LANG_MAP:
        return LANG_MAP[label]
    elif label.startswith("[") and label.endswith("]"):
        inner = label[1:-1]
        if inner.isdigit():
            return int(inner)
        else:
            raise ValueError(f"Unknown language code: {label}")
    else:
        return 1  # default to [ENG]

def round_up_to_alignment(value, alignment=0x10):
    return ((value + alignment - 1) // alignment) * alignment

def round_down_to_alignment(value, alignment=0x10):
    return value // alignment * alignment

def find_padding(data, start_offset, alignment=0x10):
    pad_start = start_offset
    while pad_start < len(data) and data[pad_start] == 0:
        pad_start += 1
    pad_size = pad_start - start_offset
    return pad_size

def extract_code_and_audio(sdt_data, text_block_start, text_block_size):
    """
    Extract:
     - Code block from end of text block (if referenced by value relative to PACB)
     - Audio/data block from after text block
    """

    # Step 1: Find PACB signature to determine base offset
    pacb_offset = sdt_data.find(b'PACB')
    if pacb_offset == -1:
        raise ValueError("PACB signature not found in template SDT")

    # Step 2: Use relative offset logic
    code_block_size_offset = pacb_offset - 4  # Relative to old 0x1C = 0x20 - 4
    if code_block_size_offset < 0:
        print(f"{Fore.RED}Error: Invalid offset for code block size.{Fore.RESET}")
        return b'', b''

    # Read code block size (relative to PACB position)
    if code_block_size_offset + 4 > len(sdt_data):
        print(f"{Fore.RED}Error: Code block size out of bounds.{Fore.RESET}")
        return b'', b''

    code_block_size = struct.unpack('<I', sdt_data[code_block_size_offset : code_block_size_offset + 4])[0]
    print(f"Code Block Size (from relative offset): 0x{code_block_size:X}")

    code_block = b''

    if code_block_size > 0:
        code_start = text_block_start + text_block_size - code_block_size
        code_block = sdt_data[code_start : code_start + code_block_size]

        # ✅ Do NOT trim code block
        trimmed_code = code_block
    else:
        trimmed_code = b''

    # Raw audio/data starts after text block
    audio_start = text_block_start + text_block_size
    audio_block = sdt_data[audio_start:]

    # Trim only leading padding from audio block
    lead_pad = find_padding(audio_block, 0)
    trimmed_audio = audio_block[lead_pad:] if lead_pad < len(audio_block) else b''

    return trimmed_code, trimmed_audio

def build_text_block_from_csv(csv_path, template_sdt_path, text_block_start):
    entries = []

    with open(template_sdt_path, 'rb') as f_template:
        f_template.seek(text_block_start)

        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                start_time = int(row['Start Time'])
                end_time = int(row['End Time'])
                lang_label = row['Lang ID']
                text = row['Text']

                lang_id = lang_label_to_id(lang_label)

                # Read original header to preserve unknown bytes
                original_header = f_template.read(16)
                if len(original_header) < 16:
                    raise ValueError("Unexpected EOF while reading headers")

                unknown_bytes = original_header[8:12]

                text_bytes = text.encode('utf-8') + b'\x00'
                entry_size = len(text_bytes) + 16

                entries.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'lang_id': lang_id,
                    'text_bytes': text_bytes,
                    'entry_size': entry_size,
                    'unknown_bytes': unknown_bytes
                })

                # Skip original text
                original_text_end = f_template.read(1)
                while original_text_end[-1:] != b'\x00' and len(original_text_end) < 0x1000:
                    original_text_end += f_template.read(1)

    # Build new text block
    new_text_block = bytearray()
    for entry in entries:
        start_time_bytes = struct.pack('<I', entry['start_time'])
        end_time_bytes = struct.pack('<I', entry['end_time'])
        unknown_bytes = entry['unknown_bytes']
        entry_size_bytes = struct.pack('<H', entry['entry_size'])
        lang_id_bytes = struct.pack('<H', entry['lang_id'])

        entry_header = start_time_bytes + end_time_bytes + unknown_bytes + entry_size_bytes + lang_id_bytes
        new_text_block.extend(entry_header)
        new_text_block.extend(entry['text_bytes'])

    return new_text_block

def pacb_rebuilder(csv_path, template_sdt_path, output_sdt_path):
    with open(template_sdt_path, 'rb') as f:
        sdt_data = bytearray(f.read())

    # Step 2: Find PACB signature
    pacb_offset = sdt_data.find(b'PACB')
    if pacb_offset == -1:
        raise ValueError("PACB signature not found in template SDT")
    print(f"{Fore.YELLOW}'PACB' signature found at offset: 0x{pacb_offset:X}{Fore.RESET}")

    text_block_start = pacb_offset + 8
    original_text_block_size = int.from_bytes(sdt_data[pacb_offset + 4:pacb_offset + 8], byteorder='little')
    print(f"{Fore.YELLOW}Original Text Block Size: 0x{original_text_block_size:X}{Fore.RESET}")

    # Step 3–4: Extract code block and audio block
    code_block, audio_block = extract_code_and_audio(sdt_data, text_block_start, original_text_block_size)

    # Step 5: Build new text block from CSV
    new_text_block = build_text_block_from_csv(csv_path, template_sdt_path, text_block_start)
    text_with_code = new_text_block + code_block
    text_block_final_size = len(text_with_code)

    # Step 6: Create temp SDT
    with tempfile.NamedTemporaryFile(delete=False) as tmp_sdt:
        tmp_sdt_path = tmp_sdt.name

        with open(tmp_sdt_path, 'wb') as out_file:
            # Step 7: Copy header up to PACB
            out_file.write(sdt_data[:pacb_offset + 8])

            # Step 8: Write new text block size at PACB + 4
            out_file.seek(pacb_offset + 4)
            out_file.write(struct.pack('<I', text_block_final_size))

            # Step 9: Write updated text block + code block at PACB + 8
            out_file.seek(pacb_offset + 8)
            out_file.write(text_with_code)

            # Step 10: Update rounded-down End Offset at PACB - 0x0C
            end_offset_unaligned = (pacb_offset + 8 + text_block_final_size) - 1
            end_offset_aligned = round_down_to_alignment(end_offset_unaligned)

            # Apply dynamic offset correction based on PACB position
            offset_correction = ((pacb_offset - 0x20) // 0x10) * 0x10
            adjusted_end_offset = end_offset_aligned - offset_correction

            print(f"PACB Offset: 0x{pacb_offset:X}, Offset Correction: -0x{offset_correction:X}")
            print(f"Unadjusted End Offset: 0x{end_offset_aligned:X} → Adjusted: 0x{adjusted_end_offset:X}")

            out_file.seek(pacb_offset - 0x0C)
            out_file.write(adjusted_end_offset.to_bytes(4, byteorder='little'))

    # Step 11: Create final SDT
    with open(tmp_sdt_path, 'rb') as tmp_in, open(output_sdt_path, 'wb') as final_out:
        final_out.write(tmp_in.read())

        # Step 14: Add padding before audio
        current_pos = final_out.tell()
        padding_needed = round_up_to_alignment(current_pos) - current_pos
        if padding_needed > 0:
            print(f"Adding {padding_needed} bytes of padding before audio.")
            final_out.write(b'\x00' * padding_needed)

        # Step 15: Append audio data
        if audio_block:
            print(f"Appending audio data of size: 0x{len(audio_block):X}")
            final_out.write(audio_block)

    os.unlink(tmp_sdt_path)
    print(f"{Fore.CYAN}Successfully rebuilt SDT. Output saved to '{output_sdt_path}'.{Fore.RESET}")

# Entry point
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"{Fore.CYAN}Usage: Tool.py input.csv output.sdt{Fore.RESET}")
        sys.exit(1)

    csv_path = sys.argv[1]
    output_sdt_path = sys.argv[2]

    if not csv_path.lower().endswith('.csv'):
        print(f"{Fore.RED}Error: First argument must be a .csv file.{Fore.RESET}")
        sys.exit(1)

    if not os.path.isfile(csv_path):
        print(f"{Fore.RED}Error: CSV file not found: {csv_path}{Fore.RESET}")
        sys.exit(1)

    if not output_sdt_path.lower().endswith('.sdt'):
        print(f"{Fore.RED}Error: Second argument must be an .sdt file.{Fore.RESET}")
        sys.exit(1)

    template_sdt_path = output_sdt_path

    if not os.path.isfile(template_sdt_path):
        print(f"{Fore.RED}Error: Template SDT file not found: {template_sdt_path}{Fore.RESET}")
        sys.exit(1)

    pacb_rebuilder(csv_path, template_sdt_path, output_sdt_path)