from database import SessionLocal, engine
import models

# Create tables if they don't exist
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

# 1. Add Products
if db.query(models.Product).count() == 0:
    products = [
        models.Product(name="Maize", category="cereal", unit="kg"),
        models.Product(name="Beans", category="legume", unit="kg"),
        models.Product(name="Tomatoes", category="vegetable", unit="kg"),
        models.Product(name="Honey", category="apiculture", unit="litre")
    ]
    db.add_all(products)
    db.commit()
    print("Products added!")

# 2. Add Advisory Articles
if db.query(models.Advisory).count() == 0:
    articles = [
        models.Advisory(
            author_id=2, 
            title="How to plant maize", 
            category="crops", 
            body="Plant maize at the start of the rainy season. Ensure proper spacing."
        ),
        models.Advisory(
            author_id=2, 
            title="Bee keeping basics", 
            category="apiculture", 
            body="Place your hives in a quiet area with plenty of flowers nearby."
        )
    ]
    db.add_all(articles)
    db.commit()
    print("Advisory articles added!")

print("Database seeding complete!")
db.close()
