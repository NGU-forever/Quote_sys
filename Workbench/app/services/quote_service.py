"""报价单核心业务服务。

提供：
1. 原子单号生成（Redis 模式优先，支持当日数据库计数安全降级）
2. 报价单创建、销售身份绑定与明细快照持久化
3. 报价单列表查询（支持销售隔离与管理员全量查询、多维度筛选与分页）
4. 单张报价单明细调取
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.redis_client import get_redis
from app.models.quote import Quote
from app.models.user import RESERVED_ADMIN_USERNAME, User
from app.schemas.quote_schemas import QuoteCreate

logger = logging.getLogger(__name__)



async def generate_quote_no(db: Session, date_str: Optional[str] = None) -> str:
    """生成正式报价单号，格式：QT-YYYYMMDD-0001。

    优先通过 Redis INCR quote:seq:QT-YYYYMMDD 实现原子自增并设置 48 小时过期；
    若 Redis 键未初始化或发生过服务重启/键剔除，先使用数据库当日最大序号进行原子初始化 (SET nx=True)，
    防止单号回绕碰撞；
    若 Redis 未启动或连接失败，则安全降级为查询数据库当日已创建单号的最大序号递增。
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")

    prefix = f"QT-{date_str}"
    redis_key = f"quote:seq:{prefix}"

    # 预先查询数据库当日已有单号的最大序号，以防 Redis 重启或键丢失后回绕碰撞
    stmt = select(Quote.quote_no).where(Quote.quote_no.like(f"{prefix}-%"))
    existing_nos = db.scalars(stmt).all()
    max_db_seq = 0
    for no in existing_nos:
        parts = no.split("-")
        if len(parts) == 3 and parts[2].isdigit():
            val = int(parts[2])
            if val > max_db_seq:
                max_db_seq = val

    # 1. 尝试使用 Redis 原子自增
    try:
        redis = await get_redis()
        if redis is not None:
            # 若键不存在，以数据库当前最大序号初始化（NX=True），确保后续自增从 max_db_seq + 1 开始
            await redis.set(redis_key, max_db_seq, nx=True, ex=86400 * 2)
            seq = await redis.incr(redis_key)
            await redis.expire(redis_key, 86400 * 2)
            return f"{prefix}-{seq:04d}"
    except Exception as e:
        logger.warning("Redis increment failed, falling back to DB: %s", e)

    # 2. 优雅降级：基于数据库当日已有单号的最大序号递增
    next_seq = max_db_seq + 1
    return f"{prefix}-{next_seq:04d}"


async def create_quote(
    db: Session,
    quote_in: QuoteCreate,
    current_user: Optional[User] = None,
) -> Quote:
    """创建并保存正式报价单。"""
    quote_no = await generate_quote_no(db)

    # 绑定销售员信息
    user_id = current_user.id if current_user else None
    sales_name = quote_in.sales_name
    if not sales_name and current_user:
        sales_name = current_user.real_name or current_user.username
    sales_phone = quote_in.sales_phone
    if not sales_phone and current_user:
        sales_phone = current_user.phone

    # 序列化 items_snapshot
    raw_snapshots = quote_in.items_snapshot or []
    serialized_snapshots = []
    for item in raw_snapshots:
        if hasattr(item, "model_dump"):
            serialized_snapshots.append(item.model_dump())
        elif isinstance(item, dict):
            serialized_snapshots.append(item)
        else:
            serialized_snapshots.append(dict(item))

    quote = Quote(
        quote_no=quote_no,
        user_id=user_id,
        sales_name=sales_name,
        sales_phone=sales_phone,
        customer_name=quote_in.customer_name,
        customer_contact=quote_in.customer_contact,
        customer_phone=quote_in.customer_phone,
        status=quote_in.status or "draft",
        total_list_price=float(quote_in.total_list_price or 0.0),
        discount_rate=float(quote_in.discount_rate) if quote_in.discount_rate is not None else None,
        final_quote_price=float(quote_in.final_quote_price or 0.0),
        valid_days=int(quote_in.valid_days or 30),
        remark=quote_in.remark,
        items_snapshot=serialized_snapshots,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def get_quotes(
    db: Session,
    current_user: User,
    keyword: Optional[str] = None,
    customer: Optional[str] = None,
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Quote], int]:
    """查询报价单列表。

    - 必须为已登录用户；
    - 销售角色数据隔离：仅能查看当前销售员自身创建的报价单；
    - 管理员 (admin/manager) 支持查看全量报价单，并可通过 user_id 过滤特定销售；
    - 支持关键字 (keyword)、客户名 (customer)、单据状态 (status) 筛选与分页。
    """
    if current_user is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")

    stmt = select(Quote)

    # 权限与数据隔离规则
    is_admin = (
        current_user.role in ("admin", "manager")
        or current_user.username == RESERVED_ADMIN_USERNAME
    )

    if not is_admin:
        # 普通销售人员强制数据隔离
        stmt = stmt.where(Quote.user_id == current_user.id)
    else:
        # 管理员支持指定销售人员过滤
        if user_id is not None:
            stmt = stmt.where(Quote.user_id == user_id)

    # 筛选条件
    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                Quote.quote_no.like(kw),
                Quote.customer_name.like(kw),
                Quote.sales_name.like(kw),
                Quote.customer_contact.like(kw),
                Quote.remark.like(kw),
            )
        )

    if customer:
        stmt = stmt.where(Quote.customer_name.like(f"%{customer.strip()}%"))

    if status:
        stmt = stmt.where(Quote.status == status.strip())

    # 计算总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # 排序与分页
    offset = max(0, (page - 1) * page_size)
    stmt = stmt.order_by(Quote.id.desc()).offset(offset).limit(page_size)
    quotes = list(db.scalars(stmt).all())

    return quotes, total


def get_quote_by_no(
    db: Session,
    quote_no: str,
    current_user: User,
) -> Quote:
    """根据 quote_no 获取单张报价单明细。

    - 必须为已登录用户（未登录抛出 401）；
    - 若报价单不存在，抛出 404；
    - 若普通销售人员尝试跨销售访问他人报价单，抛出 403 异常。
    """
    if current_user is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")

    quote = db.scalar(select(Quote).where(Quote.quote_no == quote_no))
    if not quote:
        raise HTTPException(status_code=404, detail="报价单不存在")

    is_admin = (
        current_user.role in ("admin", "manager")
        or current_user.username == RESERVED_ADMIN_USERNAME
    )
    if not is_admin and quote.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看其他销售人员的报价单")

    return quote

