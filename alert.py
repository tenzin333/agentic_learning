import requests

class SlackAlerter:
    def __init__(self, webhook_url:str):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
        if not self.enabled:
            print("[slack] no webhook configured - alerts disabled")
    
    def info(self, msg: str):
        self._send("INFO", msg)
    
    def warning(self,msg: str):
        self._send("WARNING", msg)
    
    def error(self, msg: str):
        self._send("ERROR", msg)
    
    def _send(self, level: str, msg: str):
        if not self.enabled:                      # graceful no-op
            print(f"[slack disabled] {level}: {msg}")
            return
        try:
            requests.post(
                self.webhook_url,
                json={"text": f"[{level}] {msg}"},
                timeout=10,
            ).raise_for_status()
        except requests.RequestException as e:    # Slack down -> warn, don't crash the pipeline
            print(f"[slack] failed to send alert: {e}")
            
        
    