# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from app.a2ui_utils import a2ui_callback
from app.db import get_firestore_client

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description="You are a helpful Recipe Assistant connected to a Firestore database and live recipe APIs.",
    workflow_description=(
        "Analyze the request and return structured UI when appropriate. "
        "You remember user preferences and dietary facts from previous conversations to personalize responses."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)



async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: After each turn, send the session to Memory Bank for extraction."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        logger.warning(f"Memory service not available for extraction: {e}")
    return None



def memory_bank_service_builder():
    """Service builder for Vertex AI Memory Bank integration on Agent Runtime."""
    return VertexAiMemoryBankService(
        project="qwiklabs-gcp-01-57f938af240a",
        location="us-east1",
        agent_engine_id="4457878635352686592",
    )



async def generate_recipe_image(
    recipe_name: str,
    tool_context: ToolContext,
) -> str:
    """Generates a food photograph for a recipe using the gemini-3.1-flash-lite-image model and saves it as an artifact.

    Args:
        recipe_name: Title/description of the recipe (e.g. 'Garlic Butter Lemon Chicken').
        tool_context: ADK ToolContext injected automatically by the runtime.

    Returns:
        Status message indicating the image artifact was generated and saved.
    """
    client = genai.Client(vertexai=True, project="qwiklabs-gcp-01-57f938af240a", location="global")
    prompt = f"A high quality, appetizing food photograph of {recipe_name}, professionally plated."

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        image_bytes = None
        mime_type = "image/jpeg"

        for candidate in response.candidates:
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.inline_data:
                        image_bytes = part.inline_data.data
                        if part.inline_data.mime_type:
                            mime_type = part.inline_data.mime_type
                        break

        if not image_bytes:
            return f"Failed to generate image bytes for '{recipe_name}'."

        clean_name = recipe_name.lower().replace(" ", "_").replace("'", "")
        filename = f"{clean_name}.jpg"
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        await tool_context.save_artifact(filename=filename, artifact=artifact_part)
        return f"Successfully generated recipe image for '{recipe_name}' and saved artifact as '{filename}'."
    except Exception as e:
        return f"Error generating recipe image: {str(e)}"



def fetch_mealdb_recipes(query: str) -> str:
    """Fetches live recipe details from TheMealDB public API based on a search term or ingredient.

    Args:
        query: Ingredient or meal name search term (e.g. 'chicken', 'pasta', 'salmon').

    Returns:
        Formatted string containing live recipes, categories, ingredients, and preparation steps from TheMealDB.
    """
    clean_query = query.strip().lower()
    url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(clean_query)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            meals = data.get("meals")

        if not meals:
            filter_url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={urllib.parse.quote(clean_query)}"
            req = urllib.request.Request(filter_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                filter_data = json.loads(resp.read().decode("utf-8"))
                meals = filter_data.get("meals")

        if not meals:
            return f"No live recipes found on TheMealDB for query '{query}'."

        results = []
        for meal in meals[:3]:
            name = meal.get("strMeal", "Unknown Meal")
            category = meal.get("strCategory", "General")
            area = meal.get("strArea", "")
            instructions = meal.get("strInstructions", "No instructions available.")

            ingredients = []
            for i in range(1, 21):
                ing = meal.get(f"strIngredient{i}")
                measure = meal.get(f"strMeasure{i}")
                if ing and ing.strip():
                    ingredients.append(f"{measure.strip() if measure else ''} {ing.strip()}".strip())

            ing_str = ", ".join(ingredients) if ingredients else "See online for full ingredients list"

            recipe_entry = (
                f"• **{name}** ({category}{f' - {area}' if area else ''})\n"
                f"  - Ingredients: {ing_str}\n"
                f"  - Instructions: {instructions[:300]}..."
            )
            results.append(recipe_entry)

        return "\n\n".join(results)
    except Exception as e:
        return f"Error fetching recipes from TheMealDB API: {str(e)}"


def get_recipes_by_ingredient(ingredient: str = "") -> str:
    """Reads recipes from the Firestore database, optionally filtering by ingredient.

    Args:
        ingredient: Optional ingredient keyword to filter recipes (e.g. 'chicken', 'pasta', 'beef').

    Returns:
        A formatted string list of recipes found in the Firestore database.
    """
    db = get_firestore_client()
    docs = db.collection("recipes").stream()
    recipes = []
    ing_lower = ingredient.lower().strip() if ingredient else ""

    for doc in docs:
        data = doc.to_dict()
        name = data.get("name", "Unnamed Recipe")
        main_ing = data.get("ingredient", "").lower()
        ing_list = [i.lower() for i in data.get("ingredients_list", [])]

        if ing_lower:
            if ing_lower not in main_ing and not any(ing_lower in i for i in ing_list):
                continue

        recipe_str = (
            f"• **{name}** ({data.get('prep_time_minutes', 15)} mins prep)\n"
            f"  - Main ingredient: {data.get('ingredient')}\n"
            f"  - Ingredients: {', '.join(data.get('ingredients_list', []))}\n"
            f"  - Instructions: {data.get('instructions')}"
        )
        recipes.append(recipe_str)

    if not recipes:
        if ingredient:
            return f"No recipes found in Firestore matching ingredient '{ingredient}'."
        return "No recipes found in the Firestore database."

    return "\n\n".join(recipes)


def add_recipe(
    name: str,
    ingredient: str,
    ingredients_list: list[str],
    instructions: str,
    prep_time_minutes: int = 15,
) -> str:
    """Writes a new recipe item to the Firestore database.

    Args:
        name: Title of the recipe (e.g. 'Shrimp Scampi').
        ingredient: Main ingredient category (e.g. 'shrimp').
        ingredients_list: List of ingredients required.
        instructions: Cooking instructions for the recipe.
        prep_time_minutes: Estimated preparation time in minutes.

    Returns:
        Confirmation string indicating the recipe was written to Firestore.
    """
    db = get_firestore_client()
    doc_id = name.lower().replace(" ", "-")
    doc_data = {
        "name": name,
        "ingredient": ingredient.lower().strip(),
        "ingredients_list": ingredients_list,
        "instructions": instructions,
        "prep_time_minutes": prep_time_minutes,
    }
    db.collection("recipes").document(doc_id).set(doc_data)
    return f"Successfully added recipe '{name}' to Firestore database!"


def get_nutritional_info(ingredients_list: list[str]) -> str:
    """Estimates nutritional breakdown (calories, protein, carbs, fat) for a list of ingredients.

    Args:
        ingredients_list: A list of ingredient names (e.g. ['chicken breast', 'garlic', 'butter']).

    Returns:
        A formatted string with estimated calories, protein, carbs, and fat per serving.
    """
    macro_table = {
        "chicken": {"calories": 165, "protein": 31, "carbs": 0, "fat": 3.6},
        "beef": {"calories": 250, "protein": 26, "carbs": 0, "fat": 15},
        "shrimp": {"calories": 99, "protein": 24, "carbs": 0.2, "fat": 0.3},
        "pasta": {"calories": 220, "protein": 8, "carbs": 43, "fat": 1.3},
        "avocado": {"calories": 160, "protein": 2, "carbs": 8.5, "fat": 14.7},
        "egg": {"calories": 78, "protein": 6, "carbs": 0.6, "fat": 5},
        "butter": {"calories": 102, "protein": 0.1, "carbs": 0, "fat": 11.5},
        "garlic": {"calories": 5, "protein": 0.2, "carbs": 1, "fat": 0},
        "lemon": {"calories": 12, "protein": 0.4, "carbs": 3, "fat": 0.1},
        "bread": {"calories": 80, "protein": 3, "carbs": 14, "fat": 1},
        "cheese": {"calories": 110, "protein": 7, "carbs": 1, "fat": 9},
        "tomatoes": {"calories": 20, "protein": 1, "carbs": 4, "fat": 0.2},
    }

    total_cal = 0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0

    for item in ingredients_list:
        item_lower = item.lower()
        matched = False
        for key, macros in macro_table.items():
            if key in item_lower:
                total_cal += macros["calories"]
                total_protein += macros["protein"]
                total_carbs += macros["carbs"]
                total_fat += macros["fat"]
                matched = True
                break
        if not matched:
            total_cal += 35
            total_protein += 1.0
            total_carbs += 5.0
            total_fat += 1.0

    return (
        f"Estimated Nutritional Breakdown (per serving):\n"
        f"• Calories: ~{round(total_cal)} kcal\n"
        f"• Protein: ~{round(total_protein, 1)}g\n"
        f"• Carbohydrates: ~{round(total_carbs, 1)}g\n"
        f"• Fat: ~{round(total_fat, 1)}g"
    )


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        fetch_mealdb_recipes,
        get_recipes_by_ingredient,
        add_recipe,
        get_nutritional_info,
        generate_recipe_image,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)










