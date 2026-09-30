"""Agent 候选数据 Pydantic 白名单 schema（只允许模型输出目标表字段）。"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{value!r} 不是合法数字") from None
    if n != n:  # NaN
        raise ValueError("NaN 不是合法数字")
    return int(n) if n.is_integer() else n


def _integer(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{value!r} 不是合法整数") from None
    if n != n or not n.is_integer():
        raise ValueError(f"{value!r} 不是合法整数")
    return int(n)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class ProductCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str = Field(min_length=1)
    category: Literal["device", "consumable"]
    name: str = Field(min_length=1)
    min_price: float | int | None = None
    max_price: float | int | None = None
    unit: str | None = None
    pieces_per_unit: int | None = None
    units_per_box: int | None = None
    box_price: float | int | None = None
    applicable_devices: str | None = None
    raw_price_desc: str | None = None
    remark: str | None = None
    image: str | None = None

    @field_validator(
        "min_price",
        "max_price",
        "box_price",
        mode="before",
    )
    @classmethod
    def _price(cls, value):
        return _number(value)

    @field_validator("pieces_per_unit", "units_per_box", mode="before")
    @classmethod
    def _count(cls, value):
        return _integer(value)

    @field_validator("sku_id", "name", mode="before")
    @classmethod
    def _required_text(cls, value):
        return _text(value)

    @field_validator("unit", "applicable_devices", "raw_price_desc", "remark", "image", mode="before")
    @classmethod
    def _optional_text(cls, value):
        return _text(value)


class BindingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_sku_id: str = Field(min_length=1)
    consumable_sku_id: str = Field(min_length=1)

    @field_validator("device_sku_id", "consumable_sku_id", mode="before")
    @classmethod
    def _sku_text(cls, value):
        return _text(value)


class PackageCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    sku_ids: list[str] = Field(min_length=1)
    quantities: list[float | int] = Field(min_length=1)
    std_price: float | int | None = None
    discount_price: float | int | None = None
    discount_rate: str | None = None
    device_qty: int | None = None
    consumable_qty: int | None = None
    consumable_boxes: int | None = None
    fixed_bundle: bool = False
    device_price: float | int | None = None
    note: str | None = None

    @field_validator(
        "std_price",
        "discount_price",
        "device_price",
        mode="before",
    )
    @classmethod
    def _prices(cls, value):
        return _number(value)

    @field_validator(
        "device_qty",
        "consumable_qty",
        "consumable_boxes",
        mode="before",
    )
    @classmethod
    def _counts(cls, value):
        return _integer(value)

    @field_validator("quantities", mode="before")
    @classmethod
    def _quantities(cls, value):
        if not isinstance(value, list):
            raise ValueError("quantities 必须是数组")
        return [_number(v) for v in value]

    @field_validator("fixed_bundle", mode="before")
    @classmethod
    def _fixed(cls, value):
        if isinstance(value, bool):
            return value
        if value in (0, 1, "0", "1"):
            return int(value) == 1
        raise ValueError("fixed_bundle 只允许 0/1/true/false")

    @field_validator("sku_ids", mode="before")
    @classmethod
    def _skus(cls, value):
        if not isinstance(value, list):
            raise ValueError("sku_ids 必须是数组")
        cleaned = []
        for sku in value:
            text = _text(sku)
            if text:
                cleaned.append(text)
        if not cleaned:
            raise ValueError("sku_ids 不能为空")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("套餐内 SKU 不能重复")
        return cleaned

    @field_validator("package_id", "name", "discount_rate", "note", mode="before")
    @classmethod
    def _texts(cls, value):
        return _text(value)

    @model_validator(mode="after")
    def _check_lengths(self):
        if len(self.sku_ids) != len(self.quantities):
            raise ValueError("quantities 长度必须与 sku_ids 一致")
        return self


class CandidateSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    products: list[ProductCandidate] = Field(default_factory=list)
    packages: list[PackageCandidate] = Field(default_factory=list)
    bindings: list[BindingCandidate] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)

    @field_validator("products", "packages", "bindings", "issues", mode="before")
    @classmethod
    def _list_or_empty(cls, value):
        return value if isinstance(value, list) else []
