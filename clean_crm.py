import os
import sys
import json
import re
import pandas as pd

def first_non_empty(series):
    """Returns the first non-empty string in a pandas Series or list."""
    for val in series:
        if val and str(val).strip():
            return str(val).strip()
    return ''

def parse_whapp_log(log_path):
    """Parses WhatsApp bulk action log file and maps Contact IDs / Phones to whapp succes 1 or whapp failed 1."""
    if not os.path.exists(log_path):
        print(f"Warning: WhatsApp log file not found at {log_path}")
        return {}, {}

    print(f"Reading WhatsApp bulk action log from {log_path}...")
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    records = []
    current_record = None

    for line in lines[1:]: # skip header
        match = re.match(r'^([a-zA-Z0-9]{20}),', line)
        if match:
            if current_record:
                records.append(current_record)
            current_record = line
        else:
            if current_record:
                current_record += ' ' + line.strip()

    if current_record:
        records.append(current_record)

    id_to_tag = {}
    phone_to_tag = {}

    for r in records:
        parts = r.split(',')
        cid = parts[0].strip()
        
        status = ''
        if 'Delivered' in r: status = 'Delivered'
        elif 'Read' in r: status = 'Read'
        elif 'Sent' in r: status = 'Sent'
        
        is_success = False
        if status in ['Delivered', 'Read']:
            is_success = True
        elif status == 'Sent' and 'Message Undeliverable' not in r and 'failed' not in r.lower():
            is_success = True
            
        w_tag = 'whapp succes 1' if is_success else 'whapp failed 1'
        id_to_tag[cid] = w_tag

    print(f"Successfully parsed {len(id_to_tag)} WhatsApp log records.")
    return id_to_tag, phone_to_tag

def is_junk(row):
    """Identifies test/junk records based on emails, phone numbers, or test keywords."""
    email = str(row.get('Email', '')).lower().strip()
    phone = str(row.get('Phone', '')).strip()
    biz = str(row.get('Business Name', '')).lower().strip()
    fname = str(row.get('First Name', '')).lower().strip()
    lname = str(row.get('Last Name', '')).lower().strip()
    
    # Fake/test emails
    if email in ['sdafgasdgds@gdsfgdsfg.co', 'test@test.com', 'bugtest@example.com', '3@3.ro'] or 'example.com' in email or 'gdsfgdsfg' in email:
        return True
    
    # Fake/test phone numbers
    if phone in ['+40077777777', '+40770000000', '40077777777', '40770000000']:
        return True
    
    # Test keywords in name or business name
    if 'test qa' in biz or 'bug' in fname or ('test' in fname and 'test' in lname):
        return True
    
    return False

def format_name(s):
    """Capitalizes names cleanly while handling hyphenated compound names."""
    if not s or not str(s).strip():
        return ''
    parts = str(s).strip().split()
    formatted = []
    for p in parts:
        subparts = p.split('-')
        sub_formatted = [sp.capitalize() for sp in subparts]
        formatted.append('-'.join(sub_formatted))
    return ' '.join(formatted)

def fix_email(email):
    """Cleans email address and fixes common TLD typos."""
    email = str(email).strip().lower()
    if not email:
        return ''
    if email.endswith('.con'):
        email = email[:-4] + '.com'
    elif email.endswith('.cmo'):
        email = email[:-4] + '.com'
    return email

def clean_phone(phone):
    """Standardizes phone numbers into E.164 format (+40...)."""
    p = str(phone).strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if not p:
        return ''
    if p.endswith('.0'):
        p = p[:-2]
    if not p.startswith('+'):
        if p.startswith('40'):
            p = '+' + p
        elif p.startswith('07'):
            p = '+40' + p[1:]
        elif p.startswith('7') and len(p) == 9:
            p = '+40' + p
    return p

def combine_tags(tag_series_or_list, additional_tags=None):
    """Combines all unique tags into a clean sorted comma-separated string."""
    all_tags = set()
    for t_str in tag_series_or_list:
        if t_str:
            for t in str(t_str).split(','):
                t_cleaned = t.strip()
                if t_cleaned:
                    all_tags.add(t_cleaned)
    if additional_tags:
        for at in additional_tags:
            if at and at.strip():
                all_tags.add(at.strip())
    return ', '.join(sorted(list(all_tags)))

def clean_crm_data(input_csv_path, log_csv_path, output_csv_path, updated_raw_csv_path, summary_json_path):
    print(f"Reading raw CRM data from {input_csv_path}...")
    df = pd.read_csv(input_csv_path, dtype=str).fillna('')
    total_original = len(df)
    
    # Parse WhatsApp Log
    whapp_id_map, _ = parse_whapp_log(log_csv_path)
    
    # 1. First update raw CRM dataset with WhatsApp tags
    raw_whapp_succes = 0
    raw_whapp_failed = 0
    raw_updated_tags = []
    
    for idx, row in df.iterrows():
        cid = row['Contact Id']
        w_tag = whapp_id_map.get(cid, '')
        if w_tag == 'whapp succes 1':
            raw_whapp_succes += 1
        elif w_tag == 'whapp failed 1':
            raw_whapp_failed += 1
            
        raw_updated_tags.append(combine_tags([row['Tags']], [w_tag] if w_tag else []))
        
    df['Tags'] = raw_updated_tags
    df.to_csv(updated_raw_csv_path, index=False, encoding='utf-8-sig')
    print(f"Updated raw CRM dataset with WhatsApp tags exported to {updated_raw_csv_path}")
    
    # 2. Identify junk rows for cleaned version
    df['Is_Junk'] = df.apply(is_junk, axis=1)
    junk_df = df[df['Is_Junk']].copy()
    clean_df = df[~df['Is_Junk']].copy()
    total_junk = len(junk_df)
    
    # Clean and format fields
    clean_df['First Name'] = clean_df['First Name'].apply(format_name)
    clean_df['Last Name'] = clean_df['Last Name'].apply(format_name)
    clean_df['Business Name'] = clean_df['Business Name'].apply(format_name)
    clean_df['Email'] = clean_df['Email'].apply(fix_email)
    clean_df['Phone'] = clean_df['Phone'].apply(clean_phone)
    
    # Generate normalization key for full name
    clean_df['Norm_Name'] = (clean_df['First Name'].str.lower() + ' ' + clean_df['Last Name'].str.lower()).str.strip()
    
    named_contacts = clean_df[clean_df['Norm_Name'] != ''].copy()
    unnamed_contacts = clean_df[clean_df['Norm_Name'] == ''].copy()
    
    merged_named_records = []
    
    # Group by name and merge fields
    for norm_name, group in named_contacts.groupby('Norm_Name'):
        first_name = first_non_empty(group['First Name'])
        last_name = first_non_empty(group['Last Name'])
        phone = first_non_empty(group['Phone'])
        email = first_non_empty(group['Email'])
        biz = first_non_empty(group['Business Name'])
        
        # Check WhatsApp tag across all merged rows
        group_whapp_tags = [whapp_id_map.get(cid, '') for cid in group['Contact Id']]
        w_tag = ''
        if 'whapp succes 1' in group_whapp_tags:
            w_tag = 'whapp succes 1'
        elif 'whapp failed 1' in group_whapp_tags:
            w_tag = 'whapp failed 1'
            
        tags = combine_tags(group['Tags'], [w_tag] if w_tag else [])
        
        created = first_non_empty(group.sort_values(by='Created')['Created'])
        last_activity = first_non_empty(group['Last Activity'])
        contact_id = first_non_empty(group['Contact Id'])
        
        merged_named_records.append({
            'Contact Id': contact_id,
            'First Name': first_name,
            'Last Name': last_name,
            'Phone': phone,
            'Email': email,
            'Business Name': biz,
            'Created': created,
            'Last Activity': last_activity,
            'Tags': tags
        })
        
    named_res_df = pd.DataFrame(merged_named_records)
    named_res_df = named_res_df.sort_values(by=['First Name', 'Last Name', 'Created']).reset_index(drop=True)

    unnamed_records = []
    for idx, row in unnamed_contacts.iterrows():
        cid = row['Contact Id']
        w_tag = whapp_id_map.get(cid, '')
        tags = combine_tags([row['Tags']], [w_tag] if w_tag else [])
        
        unnamed_records.append({
            'Contact Id': cid,
            'First Name': '',
            'Last Name': '',
            'Phone': row['Phone'],
            'Email': row['Email'],
            'Business Name': row['Business Name'],
            'Created': row['Created'],
            'Last Activity': row['Last Activity'],
            'Tags': tags
        })
        
    unnamed_res_df = pd.DataFrame(unnamed_records)
    if not unnamed_res_df.empty:
        unnamed_res_df = unnamed_res_df.sort_values(by=['Phone', 'Email', 'Created']).reset_index(drop=True)
        
    res_df = pd.concat([named_res_df, unnamed_res_df], ignore_index=True)
    
    # Write to CSV
    res_df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
    print(f"Cleaned CRM with WhatsApp tags exported successfully to {output_csv_path}")
    
    # Calculate stats
    total_cleaned = len(res_df)
    both_contact_info = len(res_df[(res_df['Phone'] != '') & (res_df['Email'] != '')])
    phone_only = len(res_df[(res_df['Phone'] != '') & (res_df['Email'] == '')])
    email_only = len(res_df[(res_df['Phone'] == '') & (res_df['Email'] != '')])
    merged_duplicates = total_original - total_junk - total_cleaned
    
    whapp_succes_count = len(res_df[res_df['Tags'].str.contains('whapp succes 1')])
    whapp_failed_count = len(res_df[res_df['Tags'].str.contains('whapp failed 1')])
    
    stats = {
        'total_original': total_original,
        'total_junk_removed': total_junk,
        'merged_duplicates_count': merged_duplicates,
        'total_cleaned_records': total_cleaned,
        'named_contacts_count': len(named_res_df),
        'unnamed_contacts_count': len(unnamed_res_df),
        'both_phone_and_email': both_contact_info,
        'phone_only': phone_only,
        'email_only': email_only,
        'completion_rate_percent': round((both_contact_info / total_cleaned) * 100, 1) if total_cleaned else 0,
        'whapp_total_processed': len(whapp_id_map),
        'whapp_succes_count': whapp_succes_count,
        'whapp_failed_count': whapp_failed_count
    }
    
    with open(summary_json_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
        
    print("Cleanup & WhatsApp Tagging Statistics:")
    for k, v in stats.items():
        print(f"  - {k}: {v}")

if __name__ == '__main__':
    import argparse

    base_dir = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Clean a CRM contact export and tag contacts with WhatsApp bulk-send results.")
    ap.add_argument("--contacts", default=os.path.join(base_dir, "sample", "contacts_export.csv"), help="raw CRM contact export (CSV)")
    ap.add_argument("--log", default=os.path.join(base_dir, "sample", "whatsapp_bulk_log.csv"), help="WhatsApp bulk-action log (CSV)")
    ap.add_argument("--out-dir", default=os.path.join(base_dir, "data"), help="where cleaned files are written (the dashboard reads data/)")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    clean_crm_data(
        args.contacts,
        args.log,
        os.path.join(args.out_dir, "contacts_cleaned.csv"),
        os.path.join(args.out_dir, "contacts_tagged_raw.csv"),
        os.path.join(args.out_dir, "cleaning_report.json"),
    )
