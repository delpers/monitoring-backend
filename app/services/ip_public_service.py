from fastapi import Request


def get_public_ip(request: Request):
    try:
        # Check various headers where the IP might be found
        # Start with the most common proxy headers
        if x_forwarded_for := request.headers.get("x-forwarded-for"):
            # x-forwarded-for can contain multiple IPs - the leftmost one is usually the client's
            ip = x_forwarded_for.split(",")[0].strip()
        elif x_real_ip := request.headers.get("x-real-ip"):
            ip = x_real_ip
        elif cf_connecting_ip := request.headers.get("cf-connecting-ip"):  # Cloudflare
            ip = cf_connecting_ip
        elif true_client_ip := request.headers.get(
            "true-client-ip"
        ):  # Akamai/Cloudflare
            ip = true_client_ip
        else:
            # Fallback to the direct client IP if no proxy headers are found
            ip = request.client.host if hasattr(request, "client") else None

        if not ip:
            return {"ip": "0.0.0.0", "error": "Could not determine IP address"}

        return {"ip": ip}
    except Exception as e:
        return {"ip": "0.0.0.0", "error": f"Error retrieving IP: {str(e)}"}
