# extract.py
# Usage: python3 extract.py
import pandas as pd
import requests
from bs4 import BeautifulSoup

URL = "https://en.wikipedia.org/wiki/List_of_books_banned_by_governments"

# H2 headings that are NOT countries (housekeeping sections to skip)
NON_COUNTRY_H2 = {
    "See also", "References", "Further reading", "External links", "Notes", "Citations"
}

def get_headline_text(h):
    if h is None:
        return None
    span = h.find("span", class_="mw-headline")
    return (span.get_text(strip=True) if span else h.get_text(strip=True)).strip()

def normalize_colnames(cols):
    ren = {
        "Title ": "Title",
        "Title": "Title",
        "Author(s)": "Author(s)",
        "Authors": "Author(s)",
        "Year published": "Year published",
        "Year of publication": "Year published",
        "Publication year": "Year published",
        "Year banned": "Year banned",
        "Year unbanned": "Year unbanned",
        "Type": "Type",
        "Notes": "Notes",
        "Reason": "Notes",
        "Reasons": "Notes",
        "Publisher": "Publisher",
        "Language": "Language",
        "Genre": "Genre",
        "Country": "Country of origin",
    }
    out = []
    for c in cols:
        if isinstance(c, tuple):
            c = next((x for x in c if x and x != ""), c[-1])
        c = str(c).strip()
        out.append(ren.get(c, c))
    return out

def fetch_html(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text

def main():
    html = fetch_html(URL)
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one("#mw-content-text .mw-parser-output")
    if not content:
        raise RuntimeError("Could not locate page body.")

    frames = []

    # Grab ALL wikitables, then infer their Country/Subdivision by nearest previous h2/h3
    for tbl in content.select("table.wikitable"):
        # nearest previous h2 (country)
        h2 = tbl.find_previous("h2")
        country = get_headline_text(h2)
        if not country or country in NON_COUNTRY_H2:
            continue

        # nearest previous h3 (subdivision) that belongs under the same h2
        h3 = tbl.find_previous("h3")
        subdivision = None
        if h3 is not None:
            # ensure this h3 is AFTER the h2 we found (i.e., belongs to this country section)
            h3s_h2 = h3.find_previous("h2")
            if h3s_h2 == h2:
                subdivision = get_headline_text(h3)

        # read the table
        try:
            df = pd.read_html(str(tbl), flavor="lxml")[0]
        except ValueError:
            continue

        df.columns = normalize_colnames(df.columns)

        expected = ["Title", "Author(s)", "Year published", "Year banned", "Year unbanned", "Type", "Notes"]
        for col in expected:
            if col not in df.columns:
                df[col] = pd.NA

        # Add Country/Subdivision first
        df.insert(0, "Subdivision", subdivision if subdivision else pd.NA)
        df.insert(0, "Country", country)

        # drop empty rows & trim strings
        df = df.dropna(how="all")
        for c in df.columns:
            if df[c].dtype == object:
                df[c] = df[c].astype(str).str.strip().replace({"nan": ""})

        # remove rows missing Title
        df = df[df["Title"].astype(str).str.len() > 0]

        frames.append(df)

    if not frames:
        raise RuntimeError("No tables found under country sections. The page layout may have changed.")

    out = pd.concat(frames, ignore_index=True)

    # order columns
    first = ["Country", "Subdivision", "Title", "Author(s)", "Year published", "Year banned", "Year unbanned", "Type", "Notes"]
    rest = [c for c in out.columns if c not in first]
    out = out[first + rest]

    out.to_csv("banned_books_by_governments_by_country.csv", index=False)
    print(f"Wrote {len(out)} rows -> banned_books_by_governments_by_country.csv")

if __name__ == "__main__":
    main()
