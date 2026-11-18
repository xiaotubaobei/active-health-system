"""本机维护工具：为已注册的个人账号设置角色，不创建账号或默认密码。"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.database import SessionLocal
from app.models.entities import AuthSession, User
from app.security import RESERVED_NAMES

ROLES = {"user", "prescription_specialist", "physician"}


def set_role(db, username, role):
    if role not in ROLES or username.casefold() in RESERVED_NAMES:
        raise ValueError("仅支持个人账号及 user / prescription_specialist / physician 角色")
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise ValueError("账号不存在，请先在页面注册个人账号")
    old_role = user.role
    user.role = role
    db.query(AuthSession).filter_by(user_id=user.id).delete(synchronize_session=False)
    db.commit()
    return old_role


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--role", required=True, choices=sorted(ROLES))
    args = parser.parse_args()
    with SessionLocal() as db:
        try:
            old = set_role(db, args.username.strip(), args.role)
        except ValueError as error:
            parser.exit(1, str(error) + "\n")
    print(f"{args.username}: {old} -> {args.role}；该账号需重新登录")


if __name__ == "__main__":
    main()
