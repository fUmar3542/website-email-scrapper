"""
Website Email Scraper
---------------------
Reads an Excel sheet containing website URLs,
scrapes official email addresses from:
    - Main page
    - Contact page(s)

Exports:
---------
1. scraped_emails.xlsx
   -> Websites with extracted emails

2. no_emails_found.xlsx
   -> Websites where no emails were found

3. summary.xlsx
   -> Summary counts

Requirements:
--------------
pip install pandas requests beautifulsoup4 openpyxl lxml

Input Excel:
------------
websites.xlsx

Required column:
----------------
website
"""
#
# import re
# import time
# import pandas as pd
# import requests
# from bs4 import BeautifulSoup
# from urllib.parse import urljoin
#
# # ---------------- CONFIG ---------------- #
#
# INPUT_FILE = "websites.xlsx"
#
# OUTPUT_FOUND = "scraped_emails.xlsx"
# OUTPUT_NOT_FOUND = "no_emails_found.xlsx"
# OUTPUT_SUMMARY = "summary.xlsx"
#
# HEADERS = {
#     "User-Agent": (
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#         "AppleWebKit/537.36 (KHTML, like Gecko) "
#         "Chrome/124.0 Safari/537.36"
#     )
# }
#
# CONTACT_KEYWORDS = [
#     "contact",
#     "contact-us",
#     "about",
#     "support",
#     "help",
#     "reach-us",
# ]
#
# EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
#
# # Placeholder emails to ignore
# BLOCKED_EMAILS = {
#     "user@domain.com",
#     "example@example.com",
#     "test@test.com",
#     "admin@example.com",
# }
#
# # ---------------------------------------- #
#
#
# def clean_email(email):
#     """Clean extracted email."""
#     email = email.strip().lower()
#
#     email = email.replace("mailto:", "")
#     email = email.split("?")[0]
#
#     email = email.strip(".,;:()[]{}<>")
#
#     return email
#
#
# def is_valid_email(email):
#     """Validate email."""
#
#     # Ignore placeholders
#     if email in BLOCKED_EMAILS:
#         return False
#
#     blacklist = [
#         ".png",
#         ".jpg",
#         ".jpeg",
#         ".gif",
#         ".webp",
#         "example.com",
#     ]
#
#     for item in blacklist:
#         if item in email:
#             return False
#
#     return "@" in email and "." in email
#
#
# def fetch_page(url):
#     """Fetch webpage content."""
#
#     try:
#         response = requests.get(
#             url,
#             headers=HEADERS,
#             timeout=15
#         )
#
#         if response.status_code == 200:
#             return response.text
#
#     except Exception as e:
#         print(f"Error fetching {url}: {e}")
#
#     return ""
#
#
# def extract_emails(html):
#     """Extract emails from HTML."""
#
#     found_emails = re.findall(EMAIL_REGEX, html)
#
#     cleaned_emails = set()
#
#     for email in found_emails:
#
#         email = clean_email(email)
#
#         if is_valid_email(email):
#             cleaned_emails.add(email)
#
#     return cleaned_emails
#
#
# def find_contact_pages(base_url, html):
#     """Find possible contact pages."""
#
#     soup = BeautifulSoup(html, "lxml")
#
#     contact_links = set()
#
#     for link in soup.find_all("a", href=True):
#
#         href = link["href"].lower()
#
#         if any(keyword in href for keyword in CONTACT_KEYWORDS):
#
#             full_url = urljoin(base_url, href)
#
#             contact_links.add(full_url)
#
#     return list(contact_links)
#
#
# def normalize_url(url):
#     """Ensure URL has scheme."""
#
#     if not url.startswith(("http://", "https://")):
#         url = "https://" + url
#
#     return url
#
#
# def scrape_website(url):
#     """Scrape emails from website."""
#
#     url = normalize_url(url)
#
#     all_emails = set()
#
#     print(f"\nScraping: {url}")
#
#     # ---------------- MAIN PAGE ---------------- #
#
#     main_html = fetch_page(url)
#
#     if not main_html:
#         return []
#
#     main_emails = extract_emails(main_html)
#
#     all_emails.update(main_emails)
#
#     # ---------------- CONTACT PAGES ---------------- #
#
#     contact_pages = find_contact_pages(url, main_html)
#
#     for contact_url in contact_pages:
#
#         print(f"Checking contact page: {contact_url}")
#
#         contact_html = fetch_page(contact_url)
#
#         if contact_html:
#
#             contact_emails = extract_emails(contact_html)
#
#             all_emails.update(contact_emails)
#
#         time.sleep(1)
#
#     return list(all_emails)
#
#
# def add_count_row(df, label):
#     """
#     Add unique website count at end of dataframe.
#     """
#
#     unique_count = df["website"].nunique()
#
#     count_row = {
#         "website": f"{label}: {unique_count}"
#     }
#
#     if "email" in df.columns:
#         count_row["email"] = ""
#
#     df = pd.concat(
#         [df, pd.DataFrame([count_row])],
#         ignore_index=True
#     )
#
#     return df
#
#
# def main():
#
#     # ---------------- READ INPUT ---------------- #
#
#     df = pd.read_excel(INPUT_FILE)
#
#     if "website" not in df.columns:
#         raise Exception(
#             "Excel must contain a column named 'website'"
#         )
#
#     found_results = []
#     not_found_results = []
#
#     # ---------------- SCRAPE ---------------- #
#
#     for website in df["website"].dropna():
#
#         try:
#
#             emails = scrape_website(str(website))
#
#             if emails:
#
#                 for email in emails:
#
#                     found_results.append({
#                         "website": website,
#                         "email": email
#                     })
#
#             else:
#
#                 not_found_results.append({
#                     "website": website
#                 })
#
#         except Exception as e:
#
#             print(f"Error processing {website}: {e}")
#
#             not_found_results.append({
#                 "website": website
#             })
#
#     # ---------------- DATAFRAMES ---------------- #
#
#     found_df = pd.DataFrame(found_results)
#
#     not_found_df = pd.DataFrame(not_found_results)
#
#     # ---------------- ADD COUNTS ---------------- #
#
#     if not found_df.empty:
#         found_df = add_count_row(
#             found_df,
#             "Unique websites with emails"
#         )
#
#     if not not_found_df.empty:
#         not_found_df = add_count_row(
#             not_found_df,
#             "Unique websites with no emails"
#         )
#
#     # ---------------- SUMMARY FILE ---------------- #
#
#     total_input = df["website"].nunique()
#
#     total_found = (
#         found_df["website"]
#         .iloc[:-1]
#         .nunique()
#         if not found_df.empty
#         else 0
#     )
#
#     total_not_found = (
#         not_found_df["website"]
#         .iloc[:-1]
#         .nunique()
#         if not not_found_df.empty
#         else 0
#     )
#
#     summary_df = pd.DataFrame([
#         {
#             "Metric": "Total unique websites input",
#             "Count": total_input
#         },
#         {
#             "Metric": "Websites with emails found",
#             "Count": total_found
#         },
#         {
#             "Metric": "Websites with no emails",
#             "Count": total_not_found
#         }
#     ])
#
#     # Add summary total row
#     summary_total_row = pd.DataFrame([{
#         "Metric": "Total unique websites processed",
#         "Count": total_input
#     }])
#
#     summary_df = pd.concat(
#         [summary_df, summary_total_row],
#         ignore_index=True
#     )
#
#     # ---------------- EXPORT FILES ---------------- #
#
#     if not found_df.empty:
#         found_df.to_excel(OUTPUT_FOUND, index=False)
#
#     if not not_found_df.empty:
#         not_found_df.to_excel(OUTPUT_NOT_FOUND, index=False)
#
#     summary_df.to_excel(OUTPUT_SUMMARY, index=False)
#
#     # ---------------- DONE ---------------- #
#
#     print("\nDone!")
#
#     print(f"Emails saved to: {OUTPUT_FOUND}")
#     print(f"No-email websites saved to: {OUTPUT_NOT_FOUND}")
#     print(f"Summary saved to: {OUTPUT_SUMMARY}")
#
#
# if __name__ == "__main__":
#     main()





#separating code BELOW

import pandas as pd
import os
import tkinter as tk
from tkinter import filedialog, messagebox


def main():
    # Hide the main Tkinter window
    root = tk.Tk()
    root.withdraw()

    # Ask user to select Excel file
    input_file = filedialog.askopenfilename(
        title="Select your Excel file",
        filetypes=[
            ("Excel files", "*.xlsx *.xls"),
            ("All files", "*.*")
        ]
    )

    # User cancelled
    if not input_file:
        print("No file selected.")
        return

    try:
        # Read Excel file
        df = pd.read_excel(input_file)

        # Show the actual column names
        print("Columns found in Excel file:")
        print(list(df.columns))

        # Find Primary Email column
        if "Primary Email" not in df.columns:
            messagebox.showerror(
                "Error",
                'Could not find a column named "Primary Email".\n\n'
                f"Columns found:\n{list(df.columns)}"
            )
            return

        # Clean the email column
        email_column = (
            df["Primary Email"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # Separate rows
        emailed_df = df[email_column != ""].copy()
        non_emailed_df = df[email_column == ""].copy()

        # Create Output folder next to the input Excel file
        input_folder = os.path.dirname(input_file)
        output_folder = os.path.join(input_folder, "Output")

        os.makedirs(output_folder, exist_ok=True)

        # Output files
        emailed_file = os.path.join(
            output_folder,
            "Emailed_Sheet.xlsx"
        )

        non_emailed_file = os.path.join(
            output_folder,
            "Non_Emailed_Sheet.xlsx"
        )

        # Save files
        emailed_df.to_excel(emailed_file, index=False)
        non_emailed_df.to_excel(non_emailed_file, index=False)

        # Show results
        messagebox.showinfo(
            "Success",
            f"Files created successfully!\n\n"
            f"Emailed rows: {len(emailed_df)}\n"
            f"Non-emailed rows: {len(non_emailed_df)}\n\n"
            f"Output folder:\n{output_folder}"
        )

        print("\nFiles created:")
        print(emailed_file)
        print(non_emailed_file)

    except Exception as e:
        messagebox.showerror("Error", str(e))
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
