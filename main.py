import datetime
from Bio import Entrez
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
import requests

# --- 系统环境变量读取 ---
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_RECEIVER = os.getenv('EMAIL_RECEIVER')
SMTP_SERVER = 'smtp.qq.com'

# ==========================================
# --- 统一检索参数配置区 ---
# ==========================================
CORE_KEYWORDS = [
    "omics", 
    "multi-omics", 
    "single-cell", 
    "spatial transcriptomics"
]

PUBMED_SEARCH_TERM = "(" + " OR ".join([f'"{kw}"[Title/Abstract]' for kw in CORE_KEYWORDS]) + ")"
# ==========================================


def fetch_pubmed_papers():
    """检索 PubMed 数据库的新增文献并提取链接"""
    Entrez.email = EMAIL_USER if EMAIL_USER else "default@example.com"
    handle = Entrez.esearch(db="pubmed", term=PUBMED_SEARCH_TERM, reldate=1, datetype="pdat")
    record = Entrez.read(handle)
    handle.close()
    
    ids = record["IdList"]
    if not ids:
        return "今日暂无匹配条件的 PubMed 文献收录。"

    handle = Entrez.efetch(db="pubmed", id=",".join(ids), rettype="abstract", retmode="xml")
    records = Entrez.read(handle)
    handle.close()

    summary_list = []
    for article in records['PubmedArticle']:
        title = article['MedlineCitation']['Article']['ArticleTitle']
        journal = article['MedlineCitation']['Article']['Journal']['Title']
        
        # 提取 PMID 并转化为字符串
        pmid = str(article['MedlineCitation']['PMID'])
        
        try:
            abstract = article['MedlineCitation']['Article']['Abstract']['AbstractText'][0]
        except KeyError:
            abstract = "未提供摘要。"
        
        # 将 PMID 嵌入 URL 并添加至汇总格式中
        summary_list.append(
            f"【标题】: {title}\n"
            f"【期刊】: {journal}\n"
            f"【链接】: https://pubmed.ncbi.nlm.nih.gov/{pmid}/\n"
            f"【摘要】: {abstract[:300]}...\n"
        )
    
    return "\n--------------------------------------------------\n".join(summary_list)


def fetch_preprints():
    """通过 API 检索 bioRxiv 与 medRxiv 的新增预印本"""
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    preprint_summaries = []
    servers = ['medrxiv', 'biorxiv']
    
    for server in servers:
        url = f"https://api.biorxiv.org/details/{server}/{yesterday}/{today}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if 'collection' in data and data['collection']:
                    for paper in data['collection']:
                        title = paper.get('title', '')
                        abstract = paper.get('abstract', '')
                        text_to_search = (title + " " + abstract).lower()
                        
                        if any(kw.lower() in text_to_search for kw in CORE_KEYWORDS):
                            doi = paper.get('doi', '未知')
                            preprint_summaries.append(
                                f"【平台】: {server.capitalize()}\n"
                                f"【标题】: {title}\n"
                                f"【链接】: https://doi.org/{doi}\n"
                                f"【摘要】: {abstract[:300]}...\n"
                            )
        except Exception as e:
            print(f"获取 {server} 数据时发生异常: {e}")

    if not preprint_summaries:
        return "今日暂无匹配条件的 bioRxiv/medRxiv 预印本文献。"
        
    return "\n--------------------------------------------------\n".join(preprint_summaries)


def send_email(content):
    """执行 SMTP 邮件推送"""
    subject = f'组学研究文献日报 (PubMed & Preprints) - {datetime.date.today()}'
    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = EMAIL_USER
    message['To'] = EMAIL_RECEIVER
    message['Subject'] = Header(subject, 'utf-8')

    try:
        smtp_obj = smtplib.SMTP_SSL(SMTP_SERVER, 465)
        smtp_obj.login(EMAIL_USER, EMAIL_PASS)
        smtp_obj.sendmail(EMAIL_USER, [EMAIL_RECEIVER], message.as_string())
        smtp_obj.quit()
        print("邮件推送任务执行成功。")
    except Exception as e:
        print(f"邮件推送任务失败，错误信息: {e}")


if __name__ == "__main__":
    if not all([EMAIL_USER, EMAIL_PASS, EMAIL_RECEIVER]):
        print("执行中断：系统环境变量缺失，请核查 GitHub Secrets 设定。")
    else:
        print("正在抓取 PubMed 数据...")
        pubmed_results = fetch_pubmed_papers()
        print("正在抓取预印本数据...")
        preprint_results = fetch_preprints()
        
        final_report = (
            "================ PubMed 经同行评审文献 ================\n\n"
            f"{pubmed_results}\n\n\n"
            "================ bioRxiv & medRxiv 预印本 ================\n\n"
            f"{preprint_results}"
        )
        
        send_email(final_report)
