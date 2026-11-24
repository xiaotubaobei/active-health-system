"""Read-only public deployment check; never creates accounts or training data."""
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def check(base_url, *, allow_http=False):
    parts = urlsplit(base_url)
    if (parts.scheme not in {"https", "http"} or not parts.netloc
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in {"", "/"}):
        raise ValueError("请填写网站根地址，例如 https://health.example.com")
    if parts.scheme != "https" and not allow_http:
        raise ValueError("正式部署需要 HTTPS；仅本地检查可加 --allow-http")
    base_url = base_url.rstrip("/")

    def fetch(path):
        request = Request(base_url + path, headers={"Accept": "*/*"})
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            if urlsplit(response.url).netloc != parts.netloc:
                raise ValueError("检查请求被重定向到其他网站")
            return response.status, response.headers, response.read(2_000_000)

    status, headers, body = fetch("/api/health")
    if status != 200 or "application/json" not in headers.get("Content-Type", ""):
        raise ValueError("/api/health 未返回 JSON，检查前后端代理配置")
    if json.loads(body).get("status") != "ok":
        raise ValueError("后端健康检查失败")

    for path in ("/", "/exercise", "/report"):
        status, headers, body = fetch(path)
        if status != 200 or "text/html" not in headers.get("Content-Type", "") or b'id="app"' not in body:
            raise ValueError(f"{path} 无法打开，检查前端文件和页面刷新回退")

    status, headers, body = fetch("/api/users/me")
    if status != 401 or "application/json" not in headers.get("Content-Type", ""):
        raise ValueError("未登录接口应返回 401 JSON，检查身份验证或代理路径")
    if "no-store" not in headers.get("Cache-Control", ""):
        raise ValueError("个人接口缺少禁止缓存设置")

    status, _, _ = fetch("/assets/__deployment_check_missing__.js")
    if status != 404:
        raise ValueError("不存在的静态资源应返回 404，不能返回应用首页")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="网站根地址，例如 https://health.example.com")
    parser.add_argument("--allow-http", action="store_true", help="仅供本地代理测试")
    args = parser.parse_args()
    try:
        check(args.url, allow_http=args.allow_http)
    except (ValueError, URLError, TimeoutError, OSError) as error:
        print(f"部署检查失败：{error}", file=sys.stderr)
        return 1
    print("通过：前端页面、页面刷新、API 代理、未登录拦截和禁止缓存。")
    print("仍需手机验收：注册登录、摄像头权限、模型加载、训练保存和报告回看。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
