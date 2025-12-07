from sqlmodel import SQLModel, create_engine

# 資料庫連線設定 (記得換成從環境變數讀取!)
DATABASE_URL = "postgresql://flowpay:password@localhost:5432/flowpay"
engine = create_engine(DATABASE_URL, echo=True)  # echo=True 方便你看 SQL log


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
