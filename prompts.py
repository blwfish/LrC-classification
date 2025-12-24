"""
Vision prompts for racing photography analysis.

Prompts are designed to extract structured metadata from racing images,
optimized for different racing series and use cases.
"""

# Base racing prompt template
RACING_BASE_PROMPT = """Analyze this racing photograph and extract the following information.
Return your answer as JSON with these fields:
- make: Car manufacturer (e.g., "Porsche", "BMW", "Ferrari")
- model: Specific model (e.g., "911 GT3", "Cayman GT4", "M4")
- color: Primary body color
- class: Racing class if visible (look for class stickers/badges)
- numbers: Array of car numbers visible (on doors, hood, or windshield)
{fuzzy_instruction}

Focus on clearly visible information. If something is not visible or uncertain, omit it.
Only return the JSON, no other text."""

# Porsche-specific prompt with PCA class knowledge
PORSCHE_RACING_PROMPT = """Analyze this Porsche Club of America (PCA) racing photograph.

YOU MUST COMPLETE BOTH STEPS AND RETURN BOTH car_detected AND people_detected FIELDS IN EVERY RESPONSE!

STEP 1: Determine if a car is the PRIMARY SUBJECT of this image.
car_detected should be TRUE only if a car is prominently featured as the main subject.
car_detected should be FALSE if:
- There is NO car in the image
- The car is only partially visible at the edge of the frame
- The car is a tiny part of the image (less than ~20% of the frame)
- The image is primarily showing people, pit crews, paddock scenes, or other non-car subjects
- You cannot clearly see enough of the car to identify its details

STEP 2: Check for PEOPLE in the image (REQUIRED - always check and report this field).
Scan the ENTIRE image including: foreground, background, track sides, pits, paddock, spectator areas, pit crew areas.
People include: drivers (in cars), mechanics, pit crew members, spectators, photographers, safety personnel, people at race edges.
people_detected should be TRUE if you see ANY person or people anywhere in the image.
people_detected should be FALSE only if you carefully examined the image and found absolutely no people present.

If car_detected is false, return:
{{"car_detected": false, "people_detected": <boolean>, "make": null, "model": null, "color": null, "class": null, "numbers": []}}

If a car IS the primary subject (prominently featured, clearly visible), extract information as JSON:
- car_detected: true
- people_detected: <boolean> - True if any people are visible anywhere in the image, False otherwise
- make: Should be "Porsche" (or other if not a Porsche)
- model: Specific Porsche model. Common models include:
  * 911 variants: 911, 911 GT3, 911 GT3 RS, 911 GT3 Cup, 911 RSR, 911 Carrera
  * Cayman variants: Cayman, Cayman S, Cayman GT4, Cayman GT4 RS
  * Boxster variants: Boxster, Boxster S, Boxster Spyder
  * 718 variants: 718 Cayman, 718 Boxster, 718 GT4
  * Classic: 944, 968, 928, 914
- color: The ACTUAL visible body color of the car. Describe what you see:
  * Well-known Porsche colors are fine: Guards Red, Racing Yellow, Miami Blue, Shark Blue, Python Green, etc.
  * Generic colors also fine: Red, Yellow, Blue, Green, White, Black, Orange, Purple, Pink
  * "GT Silver" is a specific light metallic silver - do NOT use it as a default for any light-colored car
  * White cars are White, not GT Silver. Light gray cars are Gray, not GT Silver.
  * Only say "GT Silver" if the car is clearly that distinctive metallic silver color
- class: ONLY include if you can clearly read a class sticker/text on the windshield or body.
  Do NOT guess the class based on the car type. Omit this field if not clearly readable.
  Valid classes: SPB, SPC, SPD, SPE, GT1-GT5, GTC1-GTC6, SP996, SP997, SP991, Stock, Improved
- numbers: Array of RACING numbers visible (typically large numbers on doors, hood, or roof)
{fuzzy_instruction}

IMPORTANT:
- Set car_detected to false unless a car is the PRIMARY SUBJECT of the image
- Paddock scenes, pit crews, people, or images where the car is only a small/partial element should return car_detected: false
- Only report what you can clearly SEE in the image - do NOT guess or hallucinate details
- Do NOT guess or infer class from car model - only report class if you read it as text
- For COLOR: Look at the actual paint. White is White, not GT Silver. Only use GT Silver for true metallic silver.
- RACING NUMBERS vs BADGES: Only report large racing numbers painted/vinyl on doors, hood, or roof.
  Do NOT report "911", "718", "GT3", "GT4", or "992" from small model badges on the car body.
  Racing numbers are typically 1-3 digits, large, and prominently displayed for competition.
- If multiple cars are visible, report all visible racing numbers
- For people_detected: Report true if you see ANY people (spectators, pit crew, drivers, mechanics, etc.) anywhere in the image

Return ONLY valid JSON, no other text."""

# Fuzzy number detection instructions
FUZZY_NUMBER_INSTRUCTION = """
- fuzzy_numbers: Array of possible alternate numbers if you see evidence of
  modified numbers (duct tape additions, covered digits, ambiguous markings).
  For example, if you see "173" but the "1" looks like it might be tape over
  another number, include both "173" and possible alternates like "73" or "273"."""

NO_FUZZY_INSTRUCTION = ""

# General racing prompt (non-Porsche specific)
GENERAL_RACING_PROMPT = """Analyze this motorsport racing photograph.

YOU MUST COMPLETE BOTH STEPS AND RETURN BOTH car_detected AND people_detected FIELDS IN EVERY RESPONSE!

STEP 1: Determine if a car is the PRIMARY SUBJECT of this image.
car_detected should be TRUE only if a car is prominently featured as the main subject.
car_detected should be FALSE if:
- There is NO car in the image
- The car is only partially visible at the edge of the frame
- The car is a tiny part of the image (less than ~20% of the frame)
- The image is primarily showing people, pit crews, paddock scenes, or other non-car subjects
- You cannot clearly see enough of the car to identify its details

STEP 2: Check for PEOPLE in the image (REQUIRED - always check and report this field).
Scan the ENTIRE image including: foreground, background, track sides, pits, paddock, spectator areas, pit crew areas.
People include: drivers (in cars), mechanics, pit crew members, spectators, photographers, safety personnel, people at race edges.
people_detected should be TRUE if you see ANY person or people anywhere in the image.
people_detected should be FALSE only if you carefully examined the image and found absolutely no people present.

If car_detected is false, return:
{{"car_detected": false, "people_detected": <boolean>, "make": null, "model": null, "color": null, "class": null, "numbers": []}}

If a car IS the primary subject (prominently featured, clearly visible), extract information as JSON:
- car_detected: true
- people_detected: <boolean> - True if any people are visible anywhere in the image, False otherwise
- make: Car manufacturer
- model: Specific model if identifiable
- color: Primary body color
- class: Racing class if visible
- numbers: Array of racing numbers visible
{fuzzy_instruction}

Common racing series class systems vary widely. Look for:
- Class stickers on windshield or body
- Series-specific livery or badges
- Number boards or door panels

IMPORTANT:
- For people_detected: Report true if you see ANY people (spectators, pit crew, drivers, mechanics, etc.) anywhere in the image

Return ONLY valid JSON, no other text."""

# College sports prompt (placeholder for future)
COLLEGE_SPORTS_PROMPT = """Analyze this college sports photograph.

Extract information as JSON:
- sport: The sport being played
- team: Team name if visible (on jerseys, field, etc.)
- colors: Team colors visible
- numbers: Jersey numbers visible
- action: Brief description of the action

Return ONLY valid JSON, no other text."""


def get_prompt(profile: str, fuzzy_numbers: bool = False) -> str:
    """
    Get the appropriate prompt for a given profile.

    Args:
        profile: One of 'racing-porsche', 'racing-general', 'college-sports'
        fuzzy_numbers: Whether to include fuzzy number detection instructions

    Returns:
        Formatted prompt string
    """
    fuzzy_instruction = FUZZY_NUMBER_INSTRUCTION if fuzzy_numbers else NO_FUZZY_INSTRUCTION

    prompts = {
        'racing-porsche': PORSCHE_RACING_PROMPT,
        'racing-general': GENERAL_RACING_PROMPT,
        'college-sports': COLLEGE_SPORTS_PROMPT,
    }

    template = prompts.get(profile, PORSCHE_RACING_PROMPT)
    return template.format(fuzzy_instruction=fuzzy_instruction)


def get_available_profiles() -> list[str]:
    """Return list of available prompt profiles."""
    return ['racing-porsche', 'racing-general', 'college-sports']


# Additional specialized prompts for edge cases

NUMBER_FOCUS_PROMPT = """Focus ONLY on the racing numbers in this image.

Look for numbers on:
- Door panels (most common location)
- Hood/bonnet
- Rear bumper or deck
- Windshield (less common)
- Roof (for aerial shots)

Return JSON with:
- numbers: Array of all visible racing numbers
- locations: Where each number appears (door, hood, etc.)
- confidence: "high", "medium", or "low" for each number

Numbers may be:
- Standard vinyl/painted numbers
- Duct tape modifications (look for irregular edges)
- Magnetic number panels
- LED/digital displays (rare)

Return ONLY valid JSON."""


MODEL_FOCUS_PROMPT = """Focus ONLY on identifying the car make and model in this image.

For Porsche identification, look for:
- Overall body shape (911 vs Cayman vs Boxster silhouettes)
- Rear engine deck and tail lights
- Front fascia and headlight shape
- Model badges (usually on rear deck lid)
- Wheel designs (often model-specific)
- Generation indicators (991 vs 992, 981 vs 982)

Return JSON with:
- make: Manufacturer
- model: Specific model
- generation: Generation/year range if identifiable
- confidence: "high", "medium", or "low"

Return ONLY valid JSON."""


def get_specialized_prompt(task: str) -> str:
    """
    Get a specialized prompt for a specific task.

    Args:
        task: One of 'number', 'model'

    Returns:
        Specialized prompt string
    """
    prompts = {
        'number': NUMBER_FOCUS_PROMPT,
        'model': MODEL_FOCUS_PROMPT,
    }
    return prompts.get(task, PORSCHE_RACING_PROMPT)
