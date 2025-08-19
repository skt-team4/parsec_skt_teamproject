import shutil
import os

src = r"C:\lsj\skt_team\lsj_skt_teamproject_2\public_projects\ljm_skt_teamproject-main\ljm_skt_teamproject-main\assets\characters\그르시.png"
dst = r"C:\lsj\skt_team\lsj_skt_teamproject_2\public_projects\ljm_skt_teamproject-main\ljm_skt_teamproject-main\assets\그르시.png"

try:
    shutil.copy2(src, dst)
    print(f"Successfully copied to: {dst}")
except Exception as e:
    print(f"Error: {e}")