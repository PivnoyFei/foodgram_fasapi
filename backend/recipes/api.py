import os

import aiofiles
from fastapi import APIRouter, Body, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse, Response

from db import database
from recipes import schemas
from recipes.models import Ingredient, Recipe, Tag
from services import query_list
from settings import STATIC_ROOT, NOT_FOUND
from users.models import User
from users.utils import get_current_user
from starlette.requests import Request

recipe_router = APIRouter(prefix='/api', tags=["recipe"])
db_user = User(database)
db_tag = Tag(database)
db_ingredient = Ingredient(database)
db_recipe = Recipe(database)


async def __create_tag_ingredient(model, item, user):
    if user.is_superuser or user.is_staff is True:
        e = await model(item)
        if type(e) != int:
            e = str(e).split(": ")[-1]
            return JSONResponse(f"Incorrect {e}", status.HTTP_400_BAD_REQUEST)
        return Response(status_code=status.HTTP_200_OK)
    return Response(status_code=status.HTTP_403_FORBIDDEN)


@recipe_router.post("/tags/")
async def create_tag(tag: schemas.Tag, user: User = Depends(get_current_user)):
    return await __create_tag_ingredient(db_tag.create_tag, tag, user)


@recipe_router.get("/tags/")
@recipe_router.get("/tags/{pk}/")
async def tags(pk: int = None):
    return await db_tag.get_tags(pk) or NOT_FOUND


@recipe_router.post("/ingredients/")
async def create_ingredient(
    ingredient: schemas.Ingredient,
    user: User = Depends(get_current_user)
):
    return await __create_tag_ingredient(
        db_ingredient.create_ingredient, ingredient, user)


@recipe_router.get("/ingredients/")
@recipe_router.get("/ingredients/{pk}/")
async def ingredients(pk: int = None):
    return await db_ingredient.get_ingredient(pk) or NOT_FOUND


@recipe_router.post("/recipes/")
async def create_recipe(
    text: str = Form(...),
    name: str = Form(...),
    image: UploadFile = File(...),
    cooking_time: int = Form(...),
    ingredients: list[schemas.AmountIngredient] = Body(...),
    tags: list[int] = Form(...),
    user_dict: User = Depends(get_current_user)
):

    filename = image.filename
    if not filename.lower().endswith(('.jpg', '.jpeg', '.bmp', '.png')):
        return JSONResponse(
            {"detail": "Invalid image format"}, status.HTTP_400_BAD_REQUEST)

    try:
        async with aiofiles.open(
            os.path.join(STATIC_ROOT, filename), "wb"
        ) as buffer:
            await buffer.write(await image.read())
    except Exception:
        buffer = os.path.join(STATIC_ROOT, filename)
        if os.path.isfile(buffer):
            os.remove(buffer)
        return JSONResponse(
            {"detail": "Error image"}, status.HTTP_400_BAD_REQUEST)

    recipe_item = {
        "author_id": user_dict["id"],
        "name": name,
        "text": text,
        "image": filename,
        "cooking_time": cooking_time
    }
    pk = await db_recipe.create_recipe(
        recipe_item, ingredients, tags
    )
    return await db_recipe.get_recipe_by_id(pk)


@recipe_router.get("/recipes/")
@recipe_router.get("/recipes/{pk}/")
@recipe_router.delete("/recipes/{pk}/")
async def recipes(request: Request, pk: int = None):
    if request.method == "DELETE":
        await db_recipe.delete_recipe(pk)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if pk:
        recipe_dict = await db_recipe.get_recipe_by_id(pk)
        return recipe_dict[0] if recipe_dict else NOT_FOUND
    return await query_list(await db_recipe.get_recipe_by_id(pk))
