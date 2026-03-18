import json
import gzip
import io

def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return None
    
    # 1. Collect all (position, word) pairs
    word_list = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_list.append((pos, word))
    
    # 2. Sort by position
    word_list.sort(key=lambda x: x[0])
    
    # 3. Join them into a string
    return " ".join([word for _, word in word_list])

def main():
    input_file = "raw_openalex_work.json"
    output_file = "..\silver_openalex_data.json"
    
    try:
        print(f"Reading {input_file}...")
        
        # Open the JSON file
        with open(input_file, "r", encoding="utf-8") as f:
            record = json.load(f)
            
        # Extract fields we care about
        silver_record = {
            "id": record.get("id"),
            "doi": record.get("doi"),
            "title": record.get("title"),
            "publication_year": record.get("publication_year"),
            "type": record.get("type"),
            # RECONSTRUCT THE ABSTRACT HERE
            "abstract": reconstruct_abstract(record.get("abstract_inverted_index"))
        }

        # Save to silver file
        with open(output_file, "w", encoding="utf-8") as out_f:
            json.dump(silver_record, out_f, indent=4)
            
        print("Success!")
        print(f"Silver record saved to: {output_file}")
        print("-" * 30)
        print("Reconstructed Abstract:")
        print(silver_record["abstract"])
        print("-" * 30)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()