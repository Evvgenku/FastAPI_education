from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db_depends import get_async_db

from app.schemas import ReviewCreate, ReviewSchema
from app.models.reviews import ReviewModel
from app.models.users import User as UserModel
from app.models.products import ProductModel
from app.auth import get_current_buyer, get_current_user



router = APIRouter(
    prefix='/reviews',
    tags=['reviews']
)

router_products = APIRouter(
    prefix="/products",
    tags=["products"],
)

from sqlalchemy.sql import func

#Пересчет рейтинга продукта
async def update_product_rating(db: AsyncSession, product_id: int):
    result = await db.execute(
        select(func.avg(ReviewModel.grade)).where(
            ReviewModel.product_id == product_id,
            ReviewModel.is_active == True
        )
    )
    avg_rating = result.scalar() or 0.0
    product = await db.get(ProductModel, product_id)
    product.rating = avg_rating
    await db.commit()

#Получить все отзывы
@router.get('/', response_model=list[ReviewSchema])
async def get_all_reviews(db: AsyncSession = Depends(get_async_db)):
    reviews = await db.scalars(select(ReviewModel).where(ReviewModel.is_active == True))
    result = reviews.all()
    return result

#Получить отзыв продукта
@router_products.get('/{product_id}/reviews', response_model=list[ReviewSchema])
async def get_product_reviews(product_id: int, db: AsyncSession = Depends(get_async_db)):
    reviews = await db.scalars(select(ReviewModel).where(ReviewModel.is_active == True, ReviewModel.product_id == product_id))
    result = reviews.all()

    product = await db.scalars(select(ProductModel).where(ProductModel.is_active == True, ProductModel.id == product_id))
    product_result = product.first()

    #Проверка продукта
    if product_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

    return result

#Создать отзыв
@router.post('/', response_model=ReviewSchema)
async def create_review(review: ReviewCreate, 
                        db: AsyncSession = Depends(get_async_db), 
                        current_user: UserModel = Depends(get_current_buyer)):
    
    product = await db.scalars(select(ProductModel).where(ProductModel.is_active == True, ProductModel.id == review.product_id))
    product_result = product.first()

    #Проверить продукт
    if product_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")
    
    #Проверить наличие отзывов от текущего пользователя
    product_review = await db.scalars(select(ReviewModel).where(ReviewModel.is_active == True, 
                                                                ReviewModel.user_id == current_user.id, 
                                                                ReviewModel.product_id == review.product_id))
    product_review_result = product_review.first()

    if product_review_result is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The review already exists")
    
    #Проверка оценки
    if 0 > review.grade > 5:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Grade out of range")
    
    db_review = ReviewModel(**review.model_dump(), user_id = current_user.id)
    db.add(db_review)
    await db.commit()
    await db.refresh(db_review)

    #Пересчет рейтинга
    await update_product_rating(db, product_result.id)
    return db_review

@router.delete('/{review_id}')
async def delete_review(review_id: int, 
                        db: AsyncSession = Depends(get_async_db),
                        current_user: UserModel = Depends(get_current_user)):

    review = await db.scalars(select(ReviewModel).where(ReviewModel.is_active == True, ReviewModel.id == review_id))
    review_result = review.first()

    #Проверка существования отзыва или его активности
    if review_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Review not found')

    #Проверить активность продукта
    product = await db.scalars(select(ProductModel).where(ProductModel.is_active == True, ProductModel.id == review_result.product_id))
    product_result = product.first()

    if product_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found')
    
    #Проверить роль пользователя на админа и владельца отзыва
    if current_user.role != 'admin' and review_result.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Permissions denied')
    
    await db.execute(update(ReviewModel)
                     .where(ReviewModel.user_id == current_user.id)
                     .values(is_active = False))
    await db.commit()
    await db.refresh(review_result)
    
    #Посчитать новый рейтинг
    await update_product_rating(db, product_result.id)

    return {'message': 'Review deleted'}