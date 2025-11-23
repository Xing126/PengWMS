import requests
import re  # 用于验证bar_code是否为MD5格式

# ---------------------- 1. 先获取openid（已成功，可复用）----------------------
login_url = "http://127.0.0.1:8008/login/"
login_data = {
    "name": "yt",
    "password": "Wyt01081247!"
}
login_response = requests.post(login_url, json=login_data)
login_result = login_response.json()

# 提取openid（已确认存在，直接获取）
openid = login_result["data"]["openid"]
print(f"已获取openid：{openid}\n")

# ---------------------- 2. 用openid调用目标接口（核心步骤）----------------------
# 目标接口地址（确认端口和路径正确）
target_url = "http://127.0.0.1:8008/asn/list/skip_create/"

# 关键：请求头携带openid（若下面的键名无效，尝试替换为 X-OpenID / Authorization）
headers = {
    "OpenID": openid  # 优先尝试这个键名，这是系统常见的自定义认证头格式
}

# 目标接口需要的请求体（按之前的要求填写）
target_payload = {
    "customer": "TestCustomer",
    "creator": "yt"
}

# 发送请求
target_response = requests.post(target_url, json=target_payload, headers=headers)
print(f"1. 接口响应码：{target_response.status_code}")  # 预期是200
print(f"2. 接口响应内容：{target_response.text}\n")

# ---------------------- 3. 验证是否符合预期结果（关键检查）----------------------
if target_response.status_code == 200:
    try:
        target_result = target_response.json()

        # 检查1：是否包含 asn_status=3
        asn_status = target_result.get("asn_status") or target_result.get("data", {}).get("asn_status")
        if asn_status == 3:
            print("✅ 检查通过：asn_status = 3")
        else:
            print(f"❌ 检查失败：asn_status 应为3，实际为 {asn_status}")

        # 检查2：是否包含自动生成的 asn_code（格式如 ASN20251103001）
        asn_code = target_result.get("asn_code") or target_result.get("data", {}).get("asn_code")
        if asn_code and re.match(r"^ASN\d{8}\d{3}$", asn_code):  # 匹配 ASN+日期（8位）+序号（3位）
            print(f"✅ 检查通过：自动生成asn_code = {asn_code}")
        else:
            print(f"❌ 检查失败：asn_code 格式异常或不存在，实际为 {asn_code}")

        # 检查3：是否包含 MD5格式的 bar_code（32位字母数字组合）
        bar_code = target_result.get("bar_code") or target_result.get("data", {}).get("bar_code")
        if bar_code and re.match(r"^[a-f0-9]{32}$", bar_code.lower()):  # MD5是32位小写字母数字
            print(f"✅ 检查通过：bar_code（MD5） = {bar_code}")
        else:
            print(f"❌ 检查失败：bar_code 不是MD5格式或不存在，实际为 {bar_code}")

        # 最后提醒检查数据库
        print("\n⚠️  请手动检查数据库表 `asnlist`：确认新增记录的 `asn_status` 字段值为3")

    except Exception as e:
        print(f"❌ 响应解析失败：{str(e)}")
else:
    print(f"❌ 接口请求失败：响应码 {target_response.status_code}，请检查openid传递是否正确")