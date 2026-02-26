# Selector Customization Guide

This guide helps you update CSS selectors when the DTIC website structure changes.

## When to Update Selectors

You'll need to update selectors when:
- The scraper runs but extracts empty or null values
- Logs show "No publication links found"
- Author, organization, or other fields are missing

## How to Find the Right Selectors

### Step 1: Run with Visible Browser

```bash
python scraper.py --max-publications 1 --no-headless
```

This lets you see exactly what the scraper is doing.

### Step 2: Inspect the Page

1. While the browser is open, press **F12** to open Developer Tools
2. Click the "Select Element" tool (or press Ctrl+Shift+C)
3. Click on the element you want to scrape (e.g., a title, author name, etc.)
4. The developer tools will highlight the HTML for that element

### Step 3: Identify the Selector

Look at the highlighted HTML. You need to create a CSS selector that uniquely identifies that element.

#### Example 1: Title

```html
<h1 class="publication-detail-title">
  Example Publication Title
</h1>
```

**Possible selectors:**
- `h1.publication-detail-title` (class-based)
- `h1[class*='publication']` (partial class match)
- `h1` (tag-based, least specific)

#### Example 2: Author

```html
<div class="author-card">
  <a href="/researcher/res.123456" class="author-name">
    John Doe
  </a>
</div>
```

**Possible selectors:**
- `a.author-name`
- `a[href*='/researcher/']`
- `.author-card a`

#### Example 3: Publication Links

```html
<a href="/publication/pub.1234567890" class="result-item-link">
  <span class="title">Publication Title</span>
</a>
```

**Possible selectors:**
- `a.result-item-link`
- `a[href*='/publication/pub.']`
- `a[href*='/publication/']`

### Step 4: Update config.json

Edit `config.json` and update the appropriate selector list:

```json
{
  "selectors": {
    "title": [
      "h1.publication-detail-title",  // Try this first
      "h1[class*='title']",           // Fallback
      "h1"                            // Last resort
    ],
    "authors": [
      "a.author-name",
      "a[href*='/researcher/']",
      ".author-card a"
    ]
  }
}
```

### Step 5: Test Your Changes

```bash
python scraper.py --max-publications 1 --no-headless
```

Watch the browser and check if data is being extracted correctly.

## Common Selector Patterns

### By Class Name
```css
.classname          /* Elements with exact class */
.class1.class2      /* Elements with multiple classes */
[class*='partial']  /* Elements where class contains 'partial' */
```

### By ID
```css
#element-id         /* Element with specific ID */
```

### By Attribute
```css
a[href*='/publication/']     /* Links containing '/publication/' */
a[href^='https://']          /* Links starting with 'https://' */
a[href$='.pdf']              /* Links ending with '.pdf' */
```

### By Structure
```css
div > a              /* Direct child */
div a                /* Any descendant */
div + a              /* Next sibling */
div.parent a.child   /* Combination */
```

### By Position
```css
li:first-child       /* First child */
li:last-child        /* Last child */
li:nth-child(2)      /* Second child */
```

## Debugging Tips

### 1. Console Testing

In the browser Developer Tools console, test selectors:

```javascript
// Test if selector finds elements
document.querySelectorAll('a[href*="/publication/"]')

// See what text it extracts
document.querySelector('h1.title').textContent

// Count matches
document.querySelectorAll('.author').length
```

### 2. Check the Logs

The scraper logs everything to a timestamped log file (e.g., `20260212_093000_dtic_scraper.log`). Look for:

```
DEBUG - Extracted JavaScript data: 12345 chars
INFO - Found 25 publication links on current page
WARNING - Error extracting authors: ...
```

### 3. Use Multiple Selectors

The scraper tries each selector in order. Use a "waterfall" approach:

```json
"title": [
  ".exact-class-name",        // Most specific
  "[class*='title']",         // Less specific
  "h1",                       // Generic
  "div.header > *:first-child" // Creative fallback
]
```

## Complete Selector Reference

Update these in `config.json`:

### Publication Discovery

```json
"publication_links": [
  "a[href*='/publication/']"
]
```

**Where**: Search results page
**What**: Links to individual publication pages

### Publication Details

```json
"title": [
  "h1.publication-title",
  "h1[class*='title']"
]
```

**Where**: Individual publication page
**What**: Publication title

```json
"abstract": [
  "div.abstract",
  "div[class*='abstract']",
  "section.abstract"
]
```

**Where**: Individual publication page
**What**: Publication abstract/summary

### People & Organizations

```json
"authors": [
  "div.author",
  "a[href*='/researcher/']"
]
```

**Where**: Individual publication page
**What**: Author names and links

```json
"organizations": [
  "div.organization",
  "a[href*='/institution/']"
]
```

**Where**: Individual publication page
**What**: Affiliated organizations

### Metadata

```json
"keywords": [
  "span.keyword",
  "[class*='keyword']"
]
```

**Where**: Individual publication page
**What**: Topic keywords/tags

```json
"publication_date": [
  "span.publication-date",
  "time"
]
```

**Where**: Individual publication page
**What**: Publication date

```json
"doi": [
  "a[href*='doi.org']"
]
```

**Where**: Individual publication page
**What**: DOI link

```json
"citations_count": [
  "span.citations-count"
]
```

**Where**: Individual publication page
**What**: Number of times cited

### Navigation

```json
"next_page_button": [
  "a[aria-label='Next page']",
  "button.next",
  "[class*='pagination'] a:last-child"
]
```

**Where**: Search results page
**What**: Button/link to next page

## Advanced: JavaScript Data Extraction

Some data might be embedded in JavaScript objects. The scraper looks for:

```javascript
window.__NUXT__
window.__INITIAL_STATE__
window.__DATA__
```

To inspect these:
1. Open Developer Tools Console
2. Type `window.__NUXT__` (or other object names)
3. Expand the object to see available data
4. Update the scraper code if needed to extract from these objects

## Example: Complete Update Process

Let's say publication links changed from `/publication/` to `/pub/`:

1. **Identify the issue**:
   ```
   Log: "No publication links found on page"
   ```

2. **Inspect the page**:
   - Run with `--no-headless`
   - Press F12, inspect a publication link
   - See: `<a href="/pub/12345">...</a>`

3. **Update config.json**:
   ```json
   "publication_links": [
     "a[href*='/pub/']",        // New format
     "a[href*='/publication/']" // Old format (fallback)
   ]
   ```

4. **Test**:
   ```bash
   python scraper.py --max-publications 1 --no-headless
   ```

5. **Verify**:
   - Check logs: "Found 25 publication links"
   - Check output file has data

## Getting Help

If you're stuck:

1. Save the page HTML:
   ```javascript
   // In browser console
   copy(document.documentElement.outerHTML)
   ```

2. Save to a file for inspection

3. Check common issues:
   - Dynamic content (loaded by JavaScript after page load)
   - Authentication requirements
   - Rate limiting (wait longer between requests)
   - Changed URL structure

## Tips for Resilient Selectors

1. **Prefer semantic selectors**: Use `[aria-label='...']`, `[role='...']` when available
2. **Avoid brittle selectors**: Don't rely on deep nesting or generated class names
3. **Use partial matches**: `[class*='author']` is more flexible than `.author-card-v2-final`
4. **Test with multiple publications**: Ensure selector works across different pages
5. **Keep fallbacks**: Always have 2-3 selector options

## Common Website Changes

### Classes renamed
**Before**: `<h1 class="pub-title">`
**After**: `<h1 class="publication-title-v2">`
**Fix**: Use partial matching: `h1[class*='title']`

### Structure changed
**Before**: `<div class="author"><a>Name</a></div>`
**After**: `<span class="researcher"><a>Name</a></span>`
**Fix**: Use attribute selector: `a[href*='/researcher/']`

### JavaScript-rendered content
**Before**: HTML in page source
**After**: Loaded by JavaScript
**Fix**: Increase wait times, use explicit waits, or extract from JS objects
