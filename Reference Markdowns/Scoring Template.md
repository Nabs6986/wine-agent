
---
type: wine_tasting_note
template_version: "1.0"
tags:
  - wine-agent
  - tasting-note
  # Add more: region/producer/grape/style/vintage/etc.
created: "{{date}}"
updated: "{{date}}"
source: "manual" # manual | inbox-converted | imported
status: "draft" # draft | published
inbox_item_id: null
wine:
  producer: ""
  cuvee: ""
  vintage: null
  country: ""
  region: ""
  subregion: ""
  appellation: ""
  vineyard: ""
  grapes: []         # e.g., "Nebbiolo"
  color: ""          # red | white | rose | orange | sparkling | fortified | other
  style: ""          # still | sparkling | fortified | other
  sweetness: ""      # bone_dry | dry | off_dry | medium | sweet | very_sweet
  alcohol_percent: null
  closure: ""        # cork | screwcap | synthetic | other
  bottle_size_ml: 750
purchase:
  price_usd: null
  store: ""
  purchase_date: null
context:
  tasting_date: "{{date}}"
  location: ""
  glassware: ""
  decant: ""         # none | splash | short | long
  decant_minutes: null
  serving_temp_c: null
  companions: ""
  occasion: ""
  food_pairing: ""
  mood: ""
provenance:
  bottle_condition: ""     # pristine | suspected_heat | compromised | unknown
  storage_notes: ""
confidence:
  level: "medium"          # low | medium | high
  uncertainty_notes: ""
faults:
  present: false
  suspected: []            # e.g., "TCA", "oxidation", "VA", "Brett"
  notes: ""
readiness:
  drink_or_hold: "drink"   # drink | hold | unsure
  window_start_year: null
  window_end_year: null
  notes: ""
scores:
  system: "wine-agent-100"
  subscores:
    appearance: 0          # 0–2
    nose: 0                # 0–12
    palate: 0              # 0–20
    structure_balance: 0   # 0–20
    finish: 0              # 0–10
    typicity_complexity: 0 # 0–16
    overall_judgment: 0    # 0–20
  total: 0                 # computed or manually confirmed
  quality_band: ""         # poor | acceptable | good | very_good | outstanding
  personal_enjoyment: 0    # 0–10 (optional)
  value_for_money: 0       # 0–10 (optional)
structure_levels:
  acidity: ""              # low | med_minus | medium | med_plus | high
  tannin: ""               # low | med_minus | medium | med_plus | high | n/a
  body: ""                 # light | med_minus | medium | med_plus | full
  alcohol: ""              # low | medium | high
  sweetness: ""            # dry | off_dry | medium | sweet
  intensity: ""            # low | medium | pronounced
  oak: ""                  # none | subtle | integrated | dominant
descriptors:
  primary_fruit: []        # e.g., "cherry", "blackberry"
  secondary: []            # e.g., "oak", "vanilla", "toast"
  tertiary: []             # e.g., "leather", "tobacco", "mushroom"
  non_fruit: []            # e.g., "violet", "graphite", "smoke"
  texture: []              # e.g., "silky", "grippy"
pairing:
  suggested: []
  avoid: []
links:
  producer_site: ""
  importer: ""
  references: []
---

# {{producer}} — {{cuvee}} ({{vintage}})

## Quick Snapshot
- **Region:** {{country}} → {{region}} → {{subregion}} → {{appellation}}
- **Grapes:** {{grapes}}
- **Style:** {{color}} / {{style}} / {{sweetness}}
- **ABV:** {{alcohol_percent}}%
- **Decant:** {{decant}} ({{decant_minutes}} min)
- **Score:** **{{scores.total}} / 100** (Quality: {{scores.quality_band}})
- **Drink/Hold:** **{{readiness.drink_or_hold}}** ({{readiness.window_start_year}}–{{readiness.window_end_year}})

---

## Appearance (0–2)
- **Clarity:** ☐ hazy ☐ clear ☐ brilliant  
- **Intensity:** ☐ pale ☐ medium ☐ deep  
- **Hue:**  
  - Red: ☐ purple ☐ ruby ☐ garnet ☐ tawny  
  - White: ☐ green ☐ lemon ☐ gold ☐ amber  
- **Other observations:**  

**Notes:**  
- 

**Subscore (0–2):** {{scores.subscores.appearance}}

---

## Nose (0–12)
- **Condition:** ☐ clean ☐ suspected fault (see Faults)  
- **Intensity:** ☐ light ☐ medium ☐ pronounced  
- **Development:** ☐ youthful ☐ developing ☐ fully developed ☐ tired

### Aromas (free text)
- **Primary:**  
- **Secondary (winemaking):**  
- **Tertiary (aging):**  

### Descriptor checklist (optional)
- Fruit: ☐ citrus ☐ stone fruit ☐ orchard ☐ red fruit ☐ black fruit ☐ tropical ☐ dried  
- Floral: ☐ white flowers ☐ violet ☐ rose  
- Herbal/green: ☐ grass ☐ tomato leaf ☐ eucalyptus ☐ mint  
- Spice: ☐ pepper ☐ cinnamon ☐ clove ☐ anise  
- Oak: ☐ vanilla ☐ toast ☐ cedar ☐ coconut ☐ smoke  
- Earth/other: ☐ leather ☐ tobacco ☐ forest floor ☐ mushroom ☐ mineral/stone ☐ graphite

**Notes:**  
- 

**Subscore (0–12):** {{scores.subscores.nose}}

---

## Palate (0–20)
- **Sweetness:** ☐ dry ☐ off-dry ☐ medium ☐ sweet  
- **Acidity:** ☐ low ☐ med- ☐ medium ☐ med+ ☐ high  
- **Tannin:** ☐ low ☐ med- ☐ medium ☐ med+ ☐ high ☐ n/a  
- **Alcohol:** ☐ low ☐ medium ☐ high  
- **Body:** ☐ light ☐ med- ☐ medium ☐ med+ ☐ full  
- **Intensity:** ☐ low ☐ medium ☐ pronounced  
- **Flavor profile (free text):**  
- **Finish:** ☐ short ☐ medium ☐ long

**Notes:**  
- 

**Subscore (0–20):** {{scores.subscores.palate}}

---

## Structure & Balance (0–20)
Evaluate integration of acidity/tannin/alcohol/body/sweetness, harmony, and precision.

- **Balance:** ☐ unbalanced ☐ slightly off ☐ balanced ☐ exceptionally balanced  
- **Texture:** ☐ angular ☐ grippy ☐ plush ☐ silky ☐ energetic  
- **Oak integration:** ☐ none ☐ subtle ☐ integrated ☐ dominant

**Notes:**  
- 

**Subscore (0–20):** {{scores.subscores.structure_balance}}

---

## Finish / Length (0–10)
- **Length:** ☐ short ☐ medium ☐ long ☐ very long  
- **Quality of finish:** ☐ drying ☐ warm ☐ clean ☐ resonant

**Notes:**  
- 

**Subscore (0–10):** {{scores.subscores.finish}}

---

## Typicity & Complexity (0–16)
- **Complexity:** ☐ simple ☐ moderate ☐ complex ☐ profound  
- **Typicity:** ☐ off-type ☐ somewhat typical ☐ typical ☐ benchmark  
- **Dimension:** layering, evolution in glass, aromatic spread.

**Notes:**  
- 

**Subscore (0–16):** {{scores.subscores.typicity_complexity}}

---

## Overall Quality Judgment (0–20)
Holistic judgment: distinctiveness, pleasure, craftsmanship, and memorability.

**Notes:**  
- 

**Subscore (0–20):** {{scores.subscores.overall_judgment}}

---

## Final Score & Summary
### Computation (100-point)
**Total:** {{scores.total}} / 100  
- Appearance: {{scores.subscores.appearance}}  
- Nose: {{scores.subscores.nose}}  
- Palate: {{scores.subscores.palate}}  
- Structure & Balance: {{scores.subscores.structure_balance}}  
- Finish: {{scores.subscores.finish}}  
- Typicity & Complexity: {{scores.subscores.typicity_complexity}}  
- Overall Judgment: {{scores.subscores.overall_judgment}}

### Quality Band (guideline)
- 0–69: poor  
- 70–79: acceptable  
- 80–89: good  
- 90–94: very good  
- 95–100: outstanding  

**Quality band:** {{scores.quality_band}}

### Personal Ratings (optional)
- **Enjoyment (0–10):** {{scores.personal_enjoyment}}  
- **Value (0–10):** {{scores.value_for_money}}

### One-paragraph conclusion
- 

---

## Readiness & Cellar Notes
- **Drink/Hold:** {{readiness.drink_or_hold}}
- **Window:** {{readiness.window_start_year}}–{{readiness.window_end_year}}
- **Rationale:**  
- 

---

## Food Pairing Notes
- Worked with:  
- Want to try with:  
- 

---

## Meta
- **Confidence:** {{confidence.level}}
- **Uncertainties:**  
- 
- **Faults:** {{faults.present}} / suspected: {{faults.suspected}}
- **Raw notes (if any):**
  - 
