"""
This script decompresses the authors file, adds and email field to each author record based
on their name, and then recompresses the file.
"""

import orjson
import gzip
import random
import os

input_file = "dtic_authors_001.jsonl.gz"
output_file = "dtic_authors_001_with_emails.jsonl.gz"


# Email variations for mocking up email addresses based on author names and common domains.
domains = [
    "dtic.mil",
    "navy.mil",
    "army.mil",
    "af.mil",
    "usmc.mil",
    "university.edu",
    "us.gov",
]
email_punc = [".", "-", "_"]


def generate_email(name):
    # Generate a mock email address based on the author's name and random punctuation.
    return (
        "".join(name.replace(".", "").lower().replace(" ", random.choice(email_punc)))
        + f"@{random.choice(domains)}"
    )


try:
    # Check if the input file exists before attempting to process it.
    if not os.path.isfile(input_file):
        raise FileNotFoundError(
            f"The file {input_file} does not exist. Please check the path and try again."
        )
    with gzip.open(input_file, "rb") as f:
        with gzip.open(output_file, "wb", compresslevel=5) as out_f:
            # Processes data line by line to avoid loading the entire file into memory
            for line in f:
                data = orjson.loads(line)
                email = generate_email(data["name"])
                data["email"] = email

                # Write the modified data back to the output file in JSON Lines format.
                out_f.write(orjson.dumps(data) + b"\n")
    print(f"Processing complete. Output written to {output_file}")

    # Swap the original file with the new file if successful.
    os.replace(output_file, input_file)

except Exception as e:
    # Cleanup temp file if something goes wrong
    if os.path.exists(output_file):
        os.remove(output_file)
    print(f"An error occurred: {e}")
