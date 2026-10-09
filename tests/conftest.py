import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.update({
    "LLM_PROVIDER": "mock", "DATABASE_URL": f"sqlite:///{_tmp}/test.db", "UPLOAD_DIR": f"{_tmp}/uploads",
    "VECTOR_STORE_PATH": f"{_tmp}/no-index", "RATE_LIMIT_PER_MINUTE": "100000", "JUDGE_ENABLED": "true",
})
