"""报价单业务路由端点。

包含：
- POST /api/quotes: 创建并保存正式报价单
- GET /api/quotes: 查询报价单列表（支持销售隔离与管理员全量查询）
- GET /api/quotes/{quote_no}: 调取单张报价单明细快照
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.quote import Quote
from app.models.user import RESERVED_ADMIN_USERNAME, User
from app.schemas.quote_schemas import (
    QuoteCreate,
    QuoteListResponse,
    QuoteOut,
)
from app.services.quote_service import (
    create_quote as service_create_quote,
    get_quote_by_no,
    get_quotes,
)

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.post("", response_model=QuoteOut, status_code=201, summary="创建并保存正式报价单")
async def create_quote(
    payload: QuoteCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """创建并保存正式报价单。若已登录则自动绑定销售人员身份。"""
    try:
        quote = await service_create_quote(db, payload, current_user=current_user)
        return quote
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"保存报价单失败: {e}")


@router.get("", response_model=QuoteListResponse, summary="查询报价单列表")
def list_quotes(
    keyword: Optional[str] = Query(None, description="搜索关键字（单号/客户/销售/联系人/备注）"),
    customer: Optional[str] = Query(None, description="客户名称模糊匹配"),
    status: Optional[str] = Query(None, description="单据状态筛选"),
    user_id: Optional[int] = Query(None, description="销售人员用户 ID（仅管理员可用）"),
    page: int = Query(1, ge=1, description="当前页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """查询报价单列表，销售人员默认只能查看自己提交的单据，管理员可全量查询。"""
    quotes, total = get_quotes(
        db,
        current_user=current_user,
        keyword=keyword,
        customer=customer,
        status=status,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": quotes,
    }


@router.get("/{quote_no}", response_model=QuoteOut, summary="根据单号查询报价单详情")
def get_quote_detail(
    quote_no: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """根据单号调取报价单明细及商品快照。"""
    quote = get_quote_by_no(db, quote_no, current_user=current_user)
    if quote is None:
        # 判断是无权访问还是不存在
        raw_exist = db.scalar(select(Quote).where(Quote.quote_no == quote_no))
        if raw_exist is not None:
            raise HTTPException(status_code=403, detail="无权查看该报价单")
        raise HTTPException(status_code=404, detail="报价单不存在")

    return quote
