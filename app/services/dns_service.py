import os
import time
import dns.resolver
import dns.reversename
import socket
import logging
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
# Changed to specify database name explicitly
db = client[
    "monitoring_db"
]  # You can change "monitoring_db" to your preferred database name
collection = db.dns_records


class DNSService:
    def check_dns(self, domain: str):
        result = {}
        try:
            # Enregistrements A
            a_records = dns.resolver.resolve(domain, "A")
            result["A"] = [ip.address for ip in a_records]
            result["ReverseDNS"] = self.reverse_dns(result["A"][0])
        except:
            result["A"] = []

        # MX
        try:
            mx_records = dns.resolver.resolve(domain, "MX")
            result["MX"] = [mx.exchange.to_text() for mx in mx_records]
        except:
            result["MX"] = []

        # Vérification DNSSEC
        result["DNSSEC"] = self.check_dnssec(domain)

        # Vérification propagation / spoof
        result["Propagation_Check"] = self.propagation_check(domain)
        result["Spoofing_Check"] = self.detect_dns_spoofing(result["Propagation_Check"])

        # Historique MongoDB
        result["timestamp"] = datetime.utcnow()
        self.store_and_compare(domain, result)

        return {"domain": domain, "status": "ok", "data": result}

    def reverse_dns(self, ip):
        try:
            rev_name = dns.reversename.from_address(ip)
            reversed_dns = dns.resolver.resolve(rev_name, "PTR")
            return reversed_dns[0].to_text()
        except:
            try:
                return socket.gethostbyaddr(ip)[0]
            except:
                return "Reverse DNS failed"

    def propagation_check(self, domain):
        public_dns = {"Google": "8.8.8.8", "Cloudflare": "1.1.1.1", "Quad9": "9.9.9.9"}
        propagation_result = {}
        for provider, server in public_dns.items():
            try:
                resolver = dns.resolver.Resolver()
                resolver.nameservers = [server]
                a_records = resolver.resolve(domain, "A")
                propagation_result[provider] = [ip.address for ip in a_records]
            except:
                propagation_result[provider] = "No Answer / Error"
        return propagation_result

    def detect_dns_spoofing(self, propagation_result):
        ip_sets = []
        for provider, result in propagation_result.items():
            if isinstance(result, list):
                ip_sets.append(set(result))

        if not ip_sets:
            return "No usable data"

        first = ip_sets[0]
        for ip_set in ip_sets[1:]:
            if ip_set != first:
                return "⚠️ Potential DNS Spoofing Detected!"
        return "✅ No Spoofing Detected"

    def check_dnssec(self, domain):
        try:
            resolver = dns.resolver.Resolver()
            answer = resolver.resolve(domain, "DNSKEY", raise_on_no_answer=False)
            if answer.rrset is not None:
                return "✅ DNSSEC active"
            else:
                return "❌ DNSSEC not configured"
        except Exception as e:
            return f"❌ DNSSEC check error: {str(e)}"

    def store_and_compare(self, domain, new_result):
        last_entry = collection.find_one({"domain": domain}, sort=[("timestamp", -1)])

        if last_entry:
            old_ips = set(last_entry["data"].get("A", []))
            new_ips = set(new_result.get("A", []))
            if old_ips != new_ips:
                logger.warning(
                    f"⚠️ DNS A record changed for {domain}: {old_ips} -> {new_ips}"
                )
        else:
            logger.info(f"First time analysis for domain: {domain}")

        collection.insert_one({"domain": domain, "data": new_result})

    def run_daemon(self, domain, interval_sec=3600):
        logger.info(
            f"Starting DNS monitoring daemon for {domain} every {interval_sec} seconds..."
        )
        while True:
            self.check_dns(domain)
            logger.info(f"Sleeping {interval_sec} seconds before next check...")
            time.sleep(interval_sec)
