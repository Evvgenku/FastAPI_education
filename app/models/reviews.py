from sqlalchemy import Boolean, Text, func
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, CheckConstraint

from app.database import Base

class ReviewModel(Base):
    __tablename__='reviews'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), nullable=False)
    comment = mapped_column(Text)
    comment_date: Mapped[datetime] = mapped_column(default=func.now())
    grade: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped["ProductModel"] = relationship("ProductModel", back_populates="reviews")

    __table_args__ = (
        CheckConstraint('grade > 0 AND grade <= 5', name='grade_range_check'),
    )
