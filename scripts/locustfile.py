from locust import HttpUser, task, between
import json

class ApiUser(HttpUser):
    wait_time = between(1, 3)
    token = None
    def on_start(self):
        pass
    @task
    def chat(self):
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = {"message": "统计上周订单数", "thread_id": "", "project_id": None}
        with self.client.post("/api/chat", json=payload, headers=headers, stream=True, catch_response=True) as resp:
            if resp.status_code == 200:
                for _ in resp.iter_content():
                    break
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")
