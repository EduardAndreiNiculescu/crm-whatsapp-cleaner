// CRM Contact Manager Dashboard Logic

let rawContacts = [];
let filteredContacts = [];
let currentPage = 1;
let pageSize = 50;

function parseCSV(text) {
    const lines = text.trim().split('\n');
    if (lines.length < 2) return [];
    
    const headers = parseCSVLine(lines[0]);
    const results = [];
    
    for (let i = 1; i < lines.length; i++) {
        if (!lines[i].strip && !lines[i].trim()) continue;
        const row = parseCSVLine(lines[i]);
        if (row.length === headers.length) {
            const obj = {};
            headers.forEach((h, index) => {
                obj[h.trim()] = row[index] ? row[index].trim() : '';
            });
            results.push(obj);
        }
    }
    return results;
}

function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"') {
            inQuotes = !inQuotes;
        } else if (char === ',' && !inQuotes) {
            result.push(current.replace(/^"|"$/g, '').trim());
            current = '';
        } else {
            current += char;
        }
    }
    result.push(current.replace(/^"|"$/g, '').trim());
    return result;
}

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('data/contacts_cleaned.csv');
        const csvText = await response.text();
        rawContacts = parseCSV(csvText);
        
        try {
            const reportResp = await fetch('data/cleaning_report.json');
            const report = await reportResp.json();
            updateStatsUI(report);
        } catch (e) {
            console.log('Report JSON fallback');
        }
        
        initTagFilterOptions();
        setupEventListeners();
        applyFilters();
    } catch (err) {
        console.error('Eroare la încărcarea datelor:', err);
        document.getElementById('results-count').innerText = 'Eroare la încărcarea datelor CSV.';
    }
});

function updateStatsUI(report) {
    if (!report) return;
    document.getElementById('stat-original').innerText = Number(report.total_original).toLocaleString();
    document.getElementById('stat-cleaned').innerText = Number(report.total_cleaned_records).toLocaleString();
    document.getElementById('stat-whapp-success').innerText = Number(report.whapp_succes_count || 0).toLocaleString();
    document.getElementById('stat-whapp-failed').innerText = Number(report.whapp_failed_count || 0).toLocaleString();
    const merged = document.getElementById('stat-merged');
    if (merged) merged.innerText = `${Number(report.merged_duplicates_count || 0).toLocaleString()} duplicate comasate`;
}

function initTagFilterOptions() {
    const tagSet = new Set();
    rawContacts.forEach(c => {
        if (c.Tags) {
            c.Tags.split(',').forEach(t => {
                const cleanTag = t.trim();
                if (cleanTag) tagSet.add(cleanTag);
            });
        }
    });
    
    const tagSelect = document.getElementById('tag-filter');
    Array.from(tagSet).sort().forEach(tag => {
        const opt = document.createElement('option');
        opt.value = tag;
        opt.textContent = tag;
        tagSelect.appendChild(opt);
    });
}

function setupEventListeners() {
    const searchInput = document.getElementById('search-input');
    const clearBtn = document.getElementById('clear-search');
    
    searchInput.addEventListener('input', (e) => {
        clearBtn.style.display = e.target.value ? 'block' : 'none';
        applyFilters();
    });
    
    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearBtn.style.display = 'none';
        applyFilters();
    });
    
    document.getElementById('whapp-filter').addEventListener('change', applyFilters);
    document.getElementById('tag-filter').addEventListener('change', applyFilters);
    
    document.getElementById('page-size-select').addEventListener('change', (e) => {
        pageSize = parseInt(e.target.value, 10);
        currentPage = 1;
        renderTable();
    });
    
    document.getElementById('prev-page-btn').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderTable();
        }
    });
    
    document.getElementById('next-page-btn').addEventListener('click', () => {
        const maxPage = Math.ceil(filteredContacts.length / pageSize);
        if (currentPage < maxPage) {
            currentPage++;
            renderTable();
        }
    });
    
    document.getElementById('close-modal-btn').addEventListener('click', closeModal);
    document.getElementById('contact-modal').addEventListener('click', (e) => {
        if (e.target.id === 'contact-modal') closeModal();
    });
}

function applyFilters() {
    const query = document.getElementById('search-input').value.toLowerCase().trim();
    const whappFilter = document.getElementById('whapp-filter').value;
    const tagFilter = document.getElementById('tag-filter').value;
    
    filteredContacts = rawContacts.filter(c => {
        const fullName = `${c['First Name'] || ''} ${c['Last Name'] || ''}`.toLowerCase();
        const email = (c['Email'] || '').toLowerCase();
        const phone = (c['Phone'] || '').toLowerCase();
        const tagsStr = (c['Tags'] || '').toLowerCase();
        
        const matchesQuery = !query || 
            fullName.includes(query) || 
            email.includes(query) || 
            phone.includes(query) || 
            tagsStr.includes(query);
            
        if (!matchesQuery) return false;
        
        // WhatsApp Filter
        const tags = (c.Tags || '').split(',').map(t => t.trim());
        if (whappFilter === 'succes' && !tags.includes('whapp succes 1')) return false;
        if (whappFilter === 'failed' && !tags.includes('whapp failed 1')) return false;
        
        // Tag filter
        if (tagFilter !== 'all') {
            if (!tags.includes(tagFilter)) return false;
        }
        
        return true;
    });
    
    currentPage = 1;
    renderTable();
}

function renderTable() {
    const tbody = document.getElementById('contacts-tbody');
    tbody.innerHTML = '';
    
    const total = filteredContacts.length;
    document.getElementById('results-count').innerHTML = `Se afișează <strong>${total}</strong> contacte găsite`;
    
    const startIdx = (currentPage - 1) * pageSize;
    const pageContacts = filteredContacts.slice(startIdx, startIdx + pageSize);
    const maxPage = Math.ceil(total / pageSize) || 1;
    
    document.getElementById('page-indicator').innerText = `Pagina ${currentPage} din ${maxPage}`;
    document.getElementById('prev-page-btn').disabled = currentPage === 1;
    document.getElementById('next-page-btn').disabled = currentPage >= maxPage;
    
    if (pageContacts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 30px; color: var(--text-muted);">Niciun contact găsit conform filtrelor selectate.</td></tr>`;
        return;
    }
    
    pageContacts.forEach((c, index) => {
        const tr = document.createElement('tr');
        const fname = c['First Name'] || '';
        const lname = c['Last Name'] || '';
        const fullName = (fname || lname) ? `${fname} ${lname}`.trim() : '<em style="color:var(--text-muted)">Fără Nume (Număr Înregistrat)</em>';
        
        const initials = ((fname ? fname[0] : '') + (lname ? lname[0] : '')).toUpperCase() || 'C';
        
        const tagsArray = c.Tags ? c.Tags.split(',').map(t => t.trim()) : [];
        
        // WhatsApp Status Badge
        let whappBadge = '<span class="tag-pill" style="color:var(--text-muted)">-</span>';
        let statusDot = '<span class="dot gray"></span>';
        
        if (tagsArray.includes('whapp succes 1')) {
            whappBadge = '<span class="tag-pill whapp-succes"><i class="fa-solid fa-check" style="font-size:10px; margin-right:4px;"></i>whapp succes 1</span>';
            statusDot = '<span class="dot green" title="WhatsApp Livrat / Citit"></span>';
        } else if (tagsArray.includes('whapp failed 1')) {
            whappBadge = '<span class="tag-pill whapp-failed"><i class="fa-solid fa-xmark" style="font-size:10px; margin-right:4px;"></i>whapp failed 1</span>';
            statusDot = '<span class="dot rose" title="WhatsApp Întrerupt / Eșuat"></span>';
        }
        
        // Render tags (excluding whapp tags from main tag list column to avoid duplicate display)
        const otherTags = tagsArray.filter(t => t !== 'whapp succes 1' && t !== 'whapp failed 1');
        let tagHtml = '-';
        if (otherTags.length > 0) {
            tagHtml = otherTags.map(t => `<span class="tag-pill">${t}</span>`).join('');
        }
        
        const createdDate = c.Created ? c.Created.split('T')[0] : '-';
        
        tr.innerHTML = `
            <td>${startIdx + index + 1}</td>
            <td>
                <div class="contact-name-cell">
                    ${statusDot}
                    <div class="avatar">${initials}</div>
                    <span>${fullName}</span>
                </div>
            </td>
            <td>${whappBadge}</td>
            <td>${c.Phone ? `<a href="tel:${c.Phone}" class="phone-link"><i class="fa-solid fa-phone" style="font-size:11px; margin-right:4px;"></i>${c.Phone}</a>` : '-'}</td>
            <td>${c.Email ? `<a href="mailto:${c.Email}" class="email-link"><i class="fa-solid fa-envelope" style="font-size:11px; margin-right:4px;"></i>${c.Email}</a>` : '-'}</td>
            <td>${tagHtml}</td>
            <td>${createdDate}</td>
        `;
        
        tr.addEventListener('click', () => openModal(c));
        tbody.appendChild(tr);
    });
}

function openModal(contact) {
    const modal = document.getElementById('contact-modal');
    const modalBody = document.getElementById('modal-body');
    const fname = contact['First Name'] || '';
    const lname = contact['Last Name'] || '';
    const fullName = (fname || lname) ? `${fname} ${lname}`.trim() : 'Contact Fără Nume';
    
    document.getElementById('modal-title').innerText = fullName;
    
    let tagsHtml = '-';
    if (contact.Tags) {
        tagsHtml = contact.Tags.split(',').map(t => {
            const cleanT = t.trim();
            if (cleanT === 'whapp succes 1') return `<span class="tag-pill whapp-succes">${cleanT}</span>`;
            if (cleanT === 'whapp failed 1') return `<span class="tag-pill whapp-failed">${cleanT}</span>`;
            return `<span class="tag-pill">${cleanT}</span>`;
        }).join('');
    }
    
    modalBody.innerHTML = `
        <div class="detail-row"><span class="label">ID Contact:</span><span class="val">${contact['Contact Id'] || '-'}</span></div>
        <div class="detail-row"><span class="label">Prenume:</span><span class="val">${contact['First Name'] || '-'}</span></div>
        <div class="detail-row"><span class="label">Nume:</span><span class="val">${contact['Last Name'] || '-'}</span></div>
        <div class="detail-row"><span class="label">Telefon:</span><span class="val">${contact.Phone ? `<a href="tel:${contact.Phone}" class="phone-link">${contact.Phone}</a>` : '-'}</span></div>
        <div class="detail-row"><span class="label">Email:</span><span class="val">${contact.Email ? `<a href="mailto:${contact.Email}" class="email-link">${contact.Email}</a>` : '-'}</span></div>
        <div class="detail-row"><span class="label">Companie / Бизнес:</span><span class="val">${contact['Business Name'] || '-'}</span></div>
        <div class="detail-row"><span class="label">Data Creării:</span><span class="val">${contact.Created || '-'}</span></div>
        <div class="detail-row"><span class="label">Ultima Activitate:</span><span class="val">${contact['Last Activity'] || '-'}</span></div>
        <div class="detail-row"><span class="label">Tag-uri Aplicate:</span><span class="val">${tagsHtml}</span></div>
    `;
    
    modal.style.display = 'flex';
}

function closeModal() {
    document.getElementById('contact-modal').style.display = 'none';
}
