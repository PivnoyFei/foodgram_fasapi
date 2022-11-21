from asyncpg.exceptions import UniqueViolationError
from sqlalchemy import (CheckConstraint, Column, DateTime, ForeignKey, Integer,
                        String, Table, Text, UniqueConstraint, and_, case,
                        select)
from sqlalchemy.sql import func
from starlette.requests import Request

from db import Base, metadata
from recipes import schemas
from settings import MEDIA_URL
from users.models import User

ingredient = Table(
    "ingredient", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(200), unique=True, index=True),
    Column("measurement_unit", String(200)),
    UniqueConstraint('name', 'measurement_unit', name='unique_ingredient')
)
tag = Table(
    "tag", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(200), unique=True, index=True),
    Column("color", String(6), unique=True),
    Column("slug", String(200), unique=True, index=True),
)
recipe = Table(
    "recipe", metadata,
    Column("id", Integer, primary_key=True),
    Column("author_id", Integer, ForeignKey("users.id", ondelete='CASCADE')),
    Column("name", String(200), unique=True, index=True),
    Column("image", String(200), unique=True),
    Column("text", Text),
    Column("cooking_time", Integer),
    CheckConstraint('cooking_time > 0', name='cooking_time_check'),
    Column("pub_date", DateTime(timezone=True), default=func.now()),
)
recipe_tag = Table(
    "recipe_tag", metadata,
    Column("id", Integer, primary_key=True),
    Column("recipe_id", Integer, ForeignKey("recipe.id", ondelete='CASCADE')),
    Column("tag_id", Integer, ForeignKey("tag.id", ondelete='CASCADE')),
)
favorites = Table(
    "favorites", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete='CASCADE')),
    Column("recipe_id", Integer, ForeignKey("recipe.id", ondelete='CASCADE')),
    UniqueConstraint('user_id', 'recipe_id', name='unique_for_favorite')
)
cart = Table(
    "cart", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete='CASCADE')),
    Column("recipe_id", Integer, ForeignKey("recipe.id", ondelete='CASCADE')),
    UniqueConstraint('user_id', 'recipe_id', name='unique_for_cart')
)
amount_ingredient = Table(
    "amount_ingredient", metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "ingredient_id",
        Integer,
        ForeignKey("ingredient.id", ondelete='CASCADE')
    ),
    Column("recipe_id", Integer, ForeignKey("recipe.id", ondelete='CASCADE')),
    Column("amount", Integer),
    CheckConstraint('amount > 0', name='amount_check'),
    UniqueConstraint(
        'ingredient_id', 'recipe_id', name='unique_for_amount_ingredient')
)


class Tag(Base):
    async def create_tag(self, tag_items) -> int:
        try:
            query = (
                tag.insert().values(
                    name=tag_items.name,
                    color=tag_items.color,
                    slug=tag_items.slug,
                )
            )
            return await self.database.execute(query)
        except UniqueViolationError as e:
            return e

    async def get_tags(
        self, pk: int = None, name: str = None
    ) -> schemas.Tags | list[schemas.Tags] | None:

        query = select([tag])
        if pk:
            query = query.where(tag.c.id == pk)
            return await self.database.fetch_one(query)
        else:
            if name:
                query = query.where(tag.c.name.like(f"{name}%"))
        return await self.database.fetch_all(query)

    async def get_tags_by_recipe_id(self, pk: int) -> list[schemas.Tags]:
        tags_dict = (
            select([tag])
            .join(recipe_tag, recipe_tag.c.tag_id == tag.c.id)
            .where(recipe_tag.c.recipe_id == pk)
            .order_by(tag.c.id)
        )
        return await self.database.fetch_all(tags_dict)

    async def delete_tag(self, pk: int) -> bool:
        await self.database.execute(
            tag.delete().where(tag.c.id == pk)
        )


class Ingredient(Base):
    async def create_ingredient(self, ingredient_items) -> int:
        try:
            query = (
                ingredient.insert().values(
                    name=ingredient_items.name,
                    measurement_unit=ingredient_items.measurement_unit,
                )
            )
            return await self.database.execute(query)
        except UniqueViolationError as e:
            return e

    async def get_ingredient(
        self, pk: int = None, name: str = None
    ) -> schemas.Ingredients | list[schemas.Ingredients] | None:

        query = select([ingredient])
        if pk:
            query = query.where(ingredient.c.id == pk)
            return await self.database.fetch_one(query)
        else:
            if name:
                query = query.where(ingredient.c.name.like(f"{name}%"))
        return await self.database.fetch_all(query)

    async def delete_ingredient(self, pk: int) -> bool:
        await self.database.execute(
            ingredient.delete().where(ingredient.c.id == pk)
        )


class Amount(Base):
    async def get_amount_by_recipe_id(self, pk: int) -> list[schemas.Amount]:
        amount_dict = (
            select([ingredient, amount_ingredient.c.amount])
            .join(
                ingredient,
                amount_ingredient.c.ingredient_id == ingredient.c.id
            )
            .where(amount_ingredient.c.recipe_id == pk)
        )
        return await self.database.fetch_all(amount_dict)


class Recipe(Base):
    async def create_recipe(
        self,
        recipe_item: dict,
        ingredients: list[schemas.AmountIngredient],
        tags: list[int | str]
    ) -> int:

        try:
            recipe_id = await self.database.execute(
                recipe.insert().values(**recipe_item).returning(recipe.c.id)
            )
            tags = [{"recipe_id": recipe_id, "tag_id": i} for i in tags]
            await self.database.execute(recipe_tag.insert().values(tags))

            ingredients = [
                {
                    "recipe_id": recipe_id,
                    "ingredient_id": i["id"],
                    "amount": int(i["amount"])
                }
                for i in ingredients
            ]
            print("ingredients", ingredients)
            await self.database.execute(
                amount_ingredient.insert().values(ingredients)
            )
            return recipe_id

        except UniqueViolationError as e:
            return e

    async def check_recipe_by_id_author(
        self,
        request: Request,
        recipe_id: int = None,
        author_id: int = None,
        limit: int = None,
    ) -> list[schemas.Favorite] | None:

        query = select(
                recipe.c.id,
                recipe.c.name,
                recipe.c.image,
                recipe.c.cooking_time
            )
        if author_id:
            query = (
                query.where(recipe.c.author_id == author_id)
                .order_by(recipe.c.pub_date.desc())
            )
        if recipe_id:
            query = query.where(recipe.c.id == recipe_id)
        else:
            if limit:
                query = query.limit(limit)

        query = await self.database.fetch_all(query)

        path_image = f"{request.base_url}{MEDIA_URL}"
        if query:
            query = [dict(i) for i in query]
            for r in query:
                r["image"] = path_image + r["image"]
        return query[0] if recipe_id else query

    async def count_recipe(
        self, tags: list[int] = None,
        is_favorited: bool = True,
        is_in_cart: bool = True
    ) -> int:
        query = (
            select(func.count(recipe.c.id).label("is_count"))
            .join(
                favorites,
                favorites.c.recipe_id == recipe.c.id,
                full=is_favorited
            )
            .join(cart, cart.c.recipe_id == recipe.c.id, full=is_in_cart)
        )
        if tags.tags:
            query = (
                query
                .join(recipe_tag, recipe_tag.c.recipe_id == recipe.c.id)
                .join(tag, recipe_tag.c.tag_id == tag.c.id)
                .where(tag.c.slug.in_(tags.tags))
                .group_by(tag.c.slug)
                .distinct()
            )
        count = await self.database.fetch_one(query)
        return count[0] if count else 0

    async def get_recipe(
        self,
        pk: int = None,
        tags: list[int] = None,
        page: int = None,
        limit: int = None,
        is_favorited: bool = True,
        is_in_cart: bool = True,
        user_id: int = None,
        request: Request = None
    ) -> list[schemas.Recipe] | None:

        query = (
            select(
                recipe.c.id,
                recipe.c.name,
                recipe.c.image,
                recipe.c.author_id.label("author"),
                recipe.c.text,
                recipe.c.cooking_time,
                case(
                    [(and_(
                        user_id != None,
                        favorites.c.user_id == user_id
                    ), "True")], else_="False"
                )
                .label("is_favorited"),
                case(
                    [(and_(
                        user_id != None,
                        cart.c.user_id == user_id
                    ), "True")], else_="False"
                )
                .label("is_in_shopping_cart")
            )
            .join(
                favorites,
                favorites.c.recipe_id == recipe.c.id,
                full=is_favorited
            )
            .join(cart, cart.c.recipe_id == recipe.c.id, full=is_in_cart)
            .order_by(recipe.c.pub_date.desc())
        )
        if pk:
            query = query.where(recipe.c.id == pk)
        else:
            if tags.tags:
                query = (
                    query
                    .join(recipe_tag, recipe_tag.c.recipe_id == recipe.c.id)
                    .join(tag, recipe_tag.c.tag_id == tag.c.id)
                    .where(tag.c.slug.in_(tags.tags))
                    .group_by(recipe.c.id, favorites.c.user_id, cart.c.user_id)
                    .having(func.count(tag.c.slug) == len(tags.tags))
                )

            if limit:
                query = query.limit(limit)
                if page:
                    query = query.offset((page - 1) * limit)

        query = await self.database.fetch_all(query)
        if not query or not query[0].id:
            return []

        query = [dict(i) for i in query]
        path_image = f"{request.base_url}{MEDIA_URL}"
        for r in query:
            r["image"] = path_image + r["image"]
            r["ingredients"] = await Amount.get_amount_by_recipe_id(
                self, r["id"])
            r["tags"] = await Tag.get_tags_by_recipe_id(self, r["id"])
            r["author"] = await User.get_user_full_by_id_auth(
                self, r["author"], user_id)
        return query

    async def delete_recipe(self, pk: int):
        await self.database.execute(
            recipe.delete().where(recipe.c.id == pk)
        )


class FavoriteCart(Base):
    async def get_shopping_cart(self, user_id: int):
        query = (
            select(
                func.sum(amount_ingredient.c.amount).label("amount"),
                ingredient.c.name,
                ingredient.c.measurement_unit
            )
            .join(
                amount_ingredient,
                cart.c.recipe_id == amount_ingredient.c.recipe_id
            )
            .join(
                ingredient,
                ingredient.c.id == amount_ingredient.c.ingredient_id
            )
            .where(cart.c.user_id == user_id)
            .group_by(ingredient.c.name, ingredient.c.measurement_unit)
        )
        return await self.database.fetch_all(query)

    async def create(self, recipe_id: int, user_id: int, db_model) -> bool:
        try:
            await self.database.execute(
                db_model.insert().values(recipe_id=recipe_id, user_id=user_id)
            )
            return True
        except UniqueViolationError:
            return False

    async def delete(self, recipe_id, user_id, db_model) -> None:
        await self.database.execute(
            db_model.delete().where(
                db_model.c.recipe_id == recipe_id,
                db_model.c.user_id == user_id
            )
        )
