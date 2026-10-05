"""Seed script for Firestore recipes collection."""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-01-57f938af240a"

SEEDED_RECIPES = [
    {
        "id": "garlic-butter-lemon-chicken",
        "name": "Garlic Butter Lemon Chicken",
        "ingredient": "chicken",
        "ingredients_list": ["Chicken breast", "garlic", "butter", "lemon juice", "olive oil", "salt", "pepper", "parsley"],
        "instructions": "1. Season chicken breasts. 2. Sear in olive oil over medium-high heat for 6-7 mins per side. 3. Add garlic, butter, lemon juice. Baste 2 mins and serve!",
        "prep_time_minutes": 20,
    },
    {
        "id": "classic-tomato-basil-pasta",
        "name": "Classic Tomato Basil Pasta",
        "ingredient": "pasta",
        "ingredients_list": ["Spaghetti", "olive oil", "minced garlic", "crushed tomatoes", "fresh basil", "parmesan cheese"],
        "instructions": "1. Boil pasta in salted water. 2. Sauté garlic in olive oil, add crushed tomatoes and simmer 10 mins. 3. Toss pasta in sauce with fresh basil and parmesan!",
        "prep_time_minutes": 15,
    },
    {
        "id": "avocado-toast-poached-egg",
        "name": "Avocado Toast with Poached Egg",
        "ingredient": "avocado",
        "ingredients_list": ["Sourdough bread", "ripe avocado", "lemon juice", "chili flakes", "eggs", "salt"],
        "instructions": "1. Toast sourdough bread. 2. Mash avocado with lemon juice and salt. 3. Poach egg in simmering water for 3 mins. 4. Spread avocado on toast, top with egg!",
        "prep_time_minutes": 10,
    },
    {
        "id": "beef-broccoli-stir-fry",
        "name": "Beef and Broccoli Stir-Fry",
        "ingredient": "beef",
        "ingredients_list": ["Flank steak", "broccoli florets", "soy sauce", "sesame oil", "garlic", "ginger", "cornstarch"],
        "instructions": "1. Slice beef thinly and toss with soy sauce and cornstarch. 2. Heat sesame oil in wok, sear beef 2 mins. 3. Add garlic, ginger, and broccoli, stir-fry 4 mins until crisp-tender!",
        "prep_time_minutes": 20,
    },
]


def seed_database():
    db = firestore.Client(project=PROJECT_ID)
    recipes_ref = db.collection("recipes")

    print(f"Seeding Firestore collection 'recipes' in project '{PROJECT_ID}'...")
    for recipe in SEEDED_RECIPES:
        doc_id = recipe["id"]
        doc_data = {k: v for k, v in recipe.items() if k != "id"}
        recipes_ref.document(doc_id).set(doc_data)
        print(f"  ✓ Seeded recipe: {recipe['name']} ({doc_id})")

    print("Firestore database successfully seeded!")


if __name__ == "__main__":
    seed_database()
