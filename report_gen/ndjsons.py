import os
import json

INPUT_DIR = "output_schemes"
OUTPUT_FILE = "loan_schemes.ndjson"

def convert_to_ndjson(input_dir, output_file):
    json_files = [f for f in os.listdir(input_dir) if f.endswith(".json")]
    print(f"Found {len(json_files)} JSON scheme files.")

    with open(output_file, "w", encoding="utf-8") as ndjson_file:
        for jf in json_files:
            path = os.path.join(input_dir, jf)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Write compact JSON in one line
                ndjson_file.write(json.dumps(data, separators=(",", ":")) + "\n")

                print(f"✔ Added {jf}")

            except Exception as e:
                print(f"❌ Error reading {jf}: {e}")

    print(f"\n✨ NDJSON created: {output_file}")

if __name__ == "__main__":
    convert_to_ndjson(INPUT_DIR, OUTPUT_FILE)


