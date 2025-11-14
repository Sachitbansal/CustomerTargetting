import pandas as pd
import os
import glob

# Define paths
RAW_DATA_PATH = "data/raw"
PROCESSED_DATA_PATH = "data/csv_tables"

def convert_asc_to_csv(input_file, output_file):
    """
    Convert a single .asc file to .csv format

    Args:
        input_file (str): Path to input .asc file
        output_file (str): Path to output .csv file
    """
    try:
        # Read .asc file (semicolon-separated with quotes)
        df = pd.read_csv(input_file, sep=';', quotechar='"', dtype=str, low_memory=False)

        # Clean column names (remove whitespace)
        df.columns = df.columns.str.strip()

        # Save as .csv file
        df.to_csv(output_file, index=False)

        return len(df), df.columns.tolist()
    except Exception as e:
        print(f"   ❌ Error converting {input_file}: {str(e)}")
        return None, None


def convert_all_asc_files():
    """
    Convert all .asc files from raw data folder to .csv format
    and save them in the processed data folder
    """
    print("="*60)
    print("Converting ASC Files to CSV Format")
    print("="*60)

    # Create processed data directory if it doesn't exist
    os.makedirs(PROCESSED_DATA_PATH, exist_ok=True)

    # Find all .asc files in the raw data folder
    asc_files = glob.glob(os.path.join(RAW_DATA_PATH, "*.asc"))

    if not asc_files:
        print(f"❌ No .asc files found in {RAW_DATA_PATH}")
        return

    print(f"\n📁 Found {len(asc_files)} .asc files to convert\n")

    conversion_summary = []

    for asc_file in sorted(asc_files):
        # Get filename without extension
        filename = os.path.basename(asc_file)
        basename = os.path.splitext(filename)[0]

        # Define output CSV path
        csv_file = os.path.join(PROCESSED_DATA_PATH, f"{basename}.csv")

        print(f"🔄 Converting: {filename}")

        # Convert the file
        num_rows, columns = convert_asc_to_csv(asc_file, csv_file)

        if num_rows is not None:
            print(f"   ✅ Saved: {basename}.csv ({num_rows} rows, {len(columns)} columns)")
            conversion_summary.append({
                'filename': basename,
                'rows': num_rows,
                'columns': len(columns),
                'column_names': columns
            })
        print()

    # Print summary
    print("="*60)
    print("Conversion Complete!")
    print("="*60)
    print(f"\n📊 Summary:")
    print(f"   Total files converted: {len(conversion_summary)}")
    print(f"   Output directory: {PROCESSED_DATA_PATH}/")

    print("\n📋 Details:")
    for item in conversion_summary:
        print(f"\n   • {item['filename']}.csv")
        print(f"     - Rows: {item['rows']:,}")
        print(f"     - Columns: {item['columns']}")
        print(f"     - Column names: {', '.join(item['column_names'][:5])}", end="")
        if len(item['column_names']) > 5:
            print(f", ... ({len(item['column_names']) - 5} more)")
        else:
            print()


def main():
    """
    Main function to execute the conversion
    """
    convert_all_asc_files()


if __name__ == "__main__":
    main()