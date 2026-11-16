"""Create a transaction summary, HTML report and local email draft."""

import argparse
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path

import pandas as pd


SOURCE_COLUMNS = {
    'trade_id': 'transaction_id',
    'trade_date': 'report_date',
    'desk_region': 'region',
    'product_code': 'product',
    'booking_status': 'status',
    'amount_minor': 'amount_cents',
}
GROUP_KEYS = ['report_date', 'region']
MINIMUM_CENTS = 100
SUBJECT = 'Posted transaction summary'
SENDER = 'reports@example.invalid'
RECIPIENT = 'reviewer@example.invalid'


def eligible_transactions(transactions):
    eligible = (
        transactions['region'].notna()
        & transactions['status'].eq('posted')
        & transactions['amount_cents'].ge(MINIMUM_CENTS)
    )
    return transactions.loc[eligible]


def summarize_transactions(transactions):
    return (
        transactions.groupby(GROUP_KEYS, as_index=False, sort=False)
        .agg(transaction_count=('transaction_id', 'count'), total_cents=('amount_cents', 'sum'))
        .sort_values(GROUP_KEYS, ignore_index=True)
    )


def write_report(summary, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / 'summary.csv'
    summary.to_csv(csv_path, index=False)
    table = summary.to_html(index=False, border=0)
    (output_dir / 'report.html').write_text(
        f'<!doctype html>\n<meta charset="utf-8">\n{table}\n', encoding='utf-8'
    )

    draft = EmailMessage(policy=SMTP)
    draft['From'] = SENDER
    draft['To'] = RECIPIENT
    draft['Subject'] = SUBJECT
    draft['X-Unsent'] = '1'
    draft.set_content('This message contains an HTML report.')
    draft.add_alternative(table, subtype='html')
    draft.add_attachment(csv_path.read_bytes(), maintype='text', subtype='csv', filename=csv_path.name)
    (output_dir / 'transaction-summary.eml').write_bytes(draft.as_bytes())


def run_workflow(input_dir, output_dir):
    source = pd.read_csv(input_dir / 'transactions.csv', dtype={'trade_id': 'string', 'amount_minor': 'Int64'})
    transactions = source.rename(columns=SOURCE_COLUMNS)
    eligible = eligible_transactions(transactions)
    unique = eligible.sort_values('transaction_id', kind='stable').drop_duplicates('transaction_id')
    summary = summarize_transactions(unique)
    write_report(summary, output_dir)
    return eligible, unique, summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    run_workflow(args.input_dir, args.output_dir)
