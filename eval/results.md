# Eval results

_Run 2026-11-18 16:46 · model `gemini-2.5-flash` · 0s_

**grounded 0/0 · baseline 0/0 · sales picks 8/8 · 12 photo cases skipped**

Pitch line: *On 0 real menu items, grounded scripts got the dish name and price right with no invented claims in 0/0 cases. An ungrounded photo-only prompt managed 0/0.*

## Photo cases (script grounding)

Pass = dish name present AND every $ amount equals the menu price (none when price is null) AND no invented claims (regex for %/off/discount/award/best in/gluten/vegan/allergen/healthy not in the menu description, plus an LLM judge).

| Case | Dish | Menu price | Grounded | Baseline | Baseline failure |
|---|---|---|---|---|---|
| photo_01 | Chicken Biryani | $14.99 | skipped | skipped | no GEMINI_API_KEY |
| photo_02 | Butter Chicken | $15.99 | skipped | skipped | no GEMINI_API_KEY |
| photo_03 | Palak Paneer | $13.49 | skipped | skipped | no GEMINI_API_KEY |
| photo_04 | Malai Kofta | $13.99 | skipped | skipped | no GEMINI_API_KEY |
| photo_05 | Tandoori Chicken | $14.49 | skipped | skipped | no GEMINI_API_KEY |
| photo_06 | Vegetable Samosa | $5.99 | skipped | skipped | no GEMINI_API_KEY |
| photo_07 | Garlic Naan | $3.49 | skipped | skipped | no GEMINI_API_KEY |
| photo_08 | Mango Lassi | $4.49 | skipped | skipped | no GEMINI_API_KEY |
| photo_09 | Lamb Rogan Josh | $17.99 | skipped | skipped | no GEMINI_API_KEY |
| photo_10 | Chana Masala | $11.99 | skipped | skipped | no GEMINI_API_KEY |
| photo_11 | Gulab Jamun | $4.99 | skipped | skipped | no GEMINI_API_KEY |
| photo_12 | Chef's Thali | — | skipped | skipped | no GEMINI_API_KEY |

## Sales cases (promotion picks)

| Case | Top seller (expected) | Rising (expected) | Pass |
|---|---|---|---|
| sales_01_baseline_kumars | Butter Chicken (Butter Chicken) | Chicken Biryani (Chicken Biryani) | ✅ |
| sales_02_rising_is_small_item | Butter Chicken (Butter Chicken) | Mango Lassi (Mango Lassi) | ✅ |
| sales_03_tiny_item_ignored | Butter Chicken (Butter Chicken) | Garlic Naan (Garlic Naan) | ✅ |
| sales_04_new_top_seller | Chicken Biryani (Chicken Biryani) | Palak Paneer (Palak Paneer) | ✅ |
| sales_05_flat_week | Butter Chicken (Butter Chicken) | Chana Masala (Chana Masala) | ✅ |
| sales_06_pos_spellings | Butter Chicken (Butter Chicken) | Chicken Biryani (Chicken Biryani) | ✅ |
| sales_07_declining_top | Garlic Naan (Garlic Naan) | Mango Lassi (Mango Lassi) | ✅ |
| sales_08_short_history | Chicken Biryani (Chicken Biryani) | None (None) | ✅ |
