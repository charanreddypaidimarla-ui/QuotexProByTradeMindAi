import os

DEFAULT_INTL = "qxbroker.com"
DEFAULT_BD = "market-qx.trade"


def resolve_qx_domain() -> str:
    """
    Resolve Quotex domain based on environment configuration.

    Priority:
      1) QX_DOMAIN  - explicit full domain override
      2) QX_REGION  - "bd"/"bangladesh" => market-qx.trade
                      "intl"/"international" => qxbroker.com
      3) default    - qxbroker.com
    """
    domain = (os.environ.get("QX_DOMAIN") or "").strip()
    if domain:
        return domain

    region = (os.environ.get("QX_REGION") or "").strip().lower()
    if region in ("bd", "bangladesh"):
        return DEFAULT_BD
    if region in ("intl", "international", "int"):
        return DEFAULT_INTL

    return DEFAULT_INTL

