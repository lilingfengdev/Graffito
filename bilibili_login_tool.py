#!/usr/bin/env python3
"""Bilibili 交互式登录工具

功能：
- 扫码登录
- 短信验证码登录
- 账号密码登录
- Cookie 字符串/JSON 导入

结果：将凭证保存至 data/cookies/bilibili_{account_id}.json，
包含 SESSDATA、bili_jct、可选 DedeUserID、buvid3，供发送器使用。

依赖：bilibili-api-python
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def prompt(msg: str) -> str:
    try:
        return input(msg)
    except EOFError:
        return ""


def prompt_secret(msg: str) -> str:
    try:
        import getpass
        return getpass.getpass(msg)
    except Exception:
        return prompt(msg)


def ensure_data_dir() -> Path:
    base = Path("data/cookies")
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_credential_file(account_id: str, sessdata: str, bili_jct: str,
                         dedeuserid: Optional[str] = None, buvid3: Optional[str] = None) -> Path:
    base = ensure_data_dir()
    path = base / f"bilibili_{account_id}.json"
    data: Dict[str, Any] = {
        "SESSDATA": sessdata or "",
        "bili_jct": bili_jct or "",
    }
    if dedeuserid:
        data["DedeUserID"] = dedeuserid
    if buvid3:
        data["buvid3"] = buvid3
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


async def validate_credential(sessdata: str, bili_jct: str,
                              dedeuserid: Optional[str] = None, buvid3: Optional[str] = None) -> bool:
    try:
        from bilibili_api import Credential, user  # type: ignore
        cred = Credential(sessdata=sessdata, bili_jct=bili_jct,
                          dedeuserid=dedeuserid, buvid3=buvid3)
        # 读取自己的信息作为校验
        _ = await user.get_self_info(credential=cred)
        return True
    except Exception:
        return False


def print_qr(data_url: str):
    print("请使用 Bilibili APP 扫码登录：")
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(border=1)
        qr.add_data(data_url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        print(f"二维码URL: {data_url}")


async def login_qrcode_flow(account_id: str) -> bool:
    from bilibili_api import login  # type: ignore
    # 新版 API 可能提供一站式方法；优先尝试
    try:
        cred = await login.login_with_qrcode()
        sessdata = getattr(cred, "sessdata", None) or getattr(cred, "SESSDATA", None)
        bili_jct = getattr(cred, "bili_jct", None) or getattr(cred, "csrf", None)
        dedeuserid = getattr(cred, "dedeuserid", None) or getattr(cred, "DedeUserID", None)
        buvid3 = getattr(cred, "buvid3", None) or getattr(cred, "BUVID3", None)
        if sessdata and bili_jct:
            path = save_credential_file(account_id, sessdata, bili_jct, dedeuserid, buvid3)
            ok = await validate_credential(sessdata, bili_jct, dedeuserid, buvid3)
            print(f"登录成功，已保存至: {path}")
            print("凭证校验：", "有效" if ok else "无法确认有效性")
            return True
        print("登录失败：缺少关键字段")
        return False
    except AttributeError:
        # 兼容分步式 QR 登录（获取二维码并轮询）
        try:
            (url, oauth_key) = await login.get_qrcode()  # type: ignore
            print_qr(url)
            print("请扫描并在手机确认登录... (Ctrl+C 取消)")
            while True:
                try:
                    cred = await login.check_qrcode(oauth_key)  # type: ignore
                    sessdata = getattr(cred, "sessdata", None) or getattr(cred, "SESSDATA", None)
                    bili_jct = getattr(cred, "bili_jct", None) or getattr(cred, "csrf", None)
                    dedeuserid = getattr(cred, "dedeuserid", None) or getattr(cred, "DedeUserID", None)
                    buvid3 = getattr(cred, "buvid3", None) or getattr(cred, "BUVID3", None)
                    if sessdata and bili_jct:
                        path = save_credential_file(account_id, sessdata, bili_jct, dedeuserid, buvid3)
                        ok = await validate_credential(sessdata, bili_jct, dedeuserid, buvid3)
                        print(f"登录成功，已保存至: {path}")
                        print("凭证校验：", "有效" if ok else "无法确认有效性")
                        return True
                except Exception:
                    await asyncio.sleep(1.5)
        except Exception as e:
            print("扫码登录失败：", e)
            return False


async def login_sms_flow(account_id: str) -> bool:
    try:
        from bilibili_api import login  # type: ignore
        area = prompt("国家区号(默认86): ").strip() or "86"
        tel = prompt("手机号: ").strip()
        if not tel:
            print("手机号不能为空")
            return False
        await login.send_sms_code(tel, int(area))  # type: ignore
        code = prompt("输入短信验证码: ").strip()
        cred = await login.login_with_sms(tel, code, int(area))  # type: ignore
        sessdata = getattr(cred, "sessdata", None) or getattr(cred, "SESSDATA", None)
        bili_jct = getattr(cred, "bili_jct", None) or getattr(cred, "csrf", None)
        dedeuserid = getattr(cred, "dedeuserid", None) or getattr(cred, "DedeUserID", None)
        buvid3 = getattr(cred, "buvid3", None) or getattr(cred, "BUVID3", None)
        if sessdata and bili_jct:
            path = save_credential_file(account_id, sessdata, bili_jct, dedeuserid, buvid3)
            ok = await validate_credential(sessdata, bili_jct, dedeuserid, buvid3)
            print(f"登录成功，已保存至: {path}")
            print("凭证校验：", "有效" if ok else "无法确认有效性")
            return True
    except Exception as e:
        print("短信登录失败：", e)
    return False


async def login_password_flow(account_id: str) -> bool:
    try:
        from bilibili_api import login  # type: ignore
        username = prompt("用户名/邮箱/手机号: ").strip()
        password = prompt_secret("密码: ")
        if not username or not password:
            print("用户名或密码为空")
            return False
        cred = await login.login_with_password(username, password)  # type: ignore
        sessdata = getattr(cred, "sessdata", None) or getattr(cred, "SESSDATA", None)
        bili_jct = getattr(cred, "bili_jct", None) or getattr(cred, "csrf", None)
        dedeuserid = getattr(cred, "dedeuserid", None) or getattr(cred, "DedeUserID", None)
        buvid3 = getattr(cred, "buvid3", None) or getattr(cred, "BUVID3", None)
        if sessdata and bili_jct:
            path = save_credential_file(account_id, sessdata, bili_jct, dedeuserid, buvid3)
            ok = await validate_credential(sessdata, bili_jct, dedeuserid, buvid3)
            print(f"登录成功，已保存至: {path}")
            print("凭证校验：", "有效" if ok else "无法确认有效性")
            return True
    except Exception as e:
        print("账号密码登录失败：", e)
    return False


async def import_cookie_flow(account_id: str) -> bool:
    print("支持 Cookie 字符串（浏览器导出）或 JSON（键包含 SESSDATA/bili_jct）。")
    raw = prompt("粘贴 Cookie 或 JSON: ")
    if not raw:
        print("输入为空")
        return False
    sessdata = ""
    bili_jct = ""
    dedeuserid = None
    buvid3 = None
    try:
        obj = json.loads(raw)
        sessdata = obj.get("SESSDATA") or obj.get("sessdata") or ""
        bili_jct = obj.get("bili_jct") or obj.get("csrf") or ""
        dedeuserid = obj.get("DedeUserID") or obj.get("dedeuserid")
        buvid3 = obj.get("buvid3") or obj.get("BUVID3")
    except Exception:
        # 解析形如 "SESSDATA=...; bili_jct=...; DedeUserID=...; buvid3=..."
        parts = [p.strip() for p in raw.split(";") if p.strip()]
        kv = {}
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                kv[k.strip()] = v.strip()
        sessdata = kv.get("SESSDATA", "")
        bili_jct = kv.get("bili_jct", kv.get("csrf", ""))
        dedeuserid = kv.get("DedeUserID")
        buvid3 = kv.get("buvid3") or kv.get("BUVID3")
    if not (sessdata and bili_jct):
        print("缺少必要字段 SESSDATA 或 bili_jct")
        return False
    path = save_credential_file(account_id, sessdata, bili_jct, dedeuserid, buvid3)
    ok = await validate_credential(sessdata, bili_jct, dedeuserid, buvid3)
    print(f"已保存至: {path}")
    print("凭证校验：", "有效" if ok else "无法确认有效性")
    return True


async def main():
    # 账号标识，用于存放到 data/cookies/bilibili_{account_id}.json
    account_id = prompt("输入 account_id（用于区分保存文件，如 qq号/自定义）: ").strip()
    if not account_id:
        print("account_id 不能为空")
        return

    while True:
        print("\n选择登录方式：")
        print("1) 扫码登录")
        print("2) 短信登录")
        print("3) 账号密码登录")
        print("4) 导入 Cookie")
        print("5) 退出")
        choice = prompt("输入选项: ").strip()

        if choice == "1":
            await login_qrcode_flow(account_id)
        elif choice == "2":
            await login_sms_flow(account_id)
        elif choice == "3":
            await login_password_flow(account_id)
        elif choice == "4":
            await import_cookie_flow(account_id)
        elif choice == "5":
            break
        else:
            print("无效选项")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已取消")

