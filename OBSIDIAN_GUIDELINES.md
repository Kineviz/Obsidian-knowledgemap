# Obsidian Knowledge Mapping Guidelines

This document provides guidelines for organizing your Obsidian vault to work optimally with the Knowledge Mapping system.

## 📁 Folder Organization

**Organize notes by folders** to maintain a clean structure:

```
Your Vault/
├── People/                    # Person entities
│   ├── John Doe.md
│   ├── Jane Smith.md
│   └── Josh Roach.md
├── Companies/                 # Company entities
│   ├── Acme Corp.md
│   ├── TechFlow.md
│   └── Meritage Group.md
├── Projects/                  # Project notes
├── Meetings/                  # Meeting notes
├── GraphXRNotes/              # Notes created via API upload
│   └── (API-uploaded files)
└── _Templates/                # Template folder (excluded from processing)
    ├── Template - Person.md
    └── Template - Company.md
```

## 📝 Note Structure

### 1. **Note Naming Convention**
- **Name your notes by the entity** (Person or Company name)
- Use clear, consistent naming: `First Last.md` for people, `Company Name.md` for companies
- Avoid special characters and spaces when possible

### 2. **Metadata Section (YAML Frontmatter)**
Place metadata at the top of each note using YAML frontmatter:

---
# Person metadata example
name: "Josh Klein"
title: "Chairman, Salespush"
company: "[[Salespush]]"
email: "josh@Salespush.com"
phone: "+1-555-0323"
location: "San Francisco, CA"
tags: [person, executive, Salespush]
---

# Josh Klein

**Summary:**
Josh Klein is the Chairman of Salespush...
```

---
# Company metadata example
name: "Salespush"
industry: "Investment Management"
founded: 2020
headquarters: "San Francisco, CA"
website: "https://Salespush.com"
tags: [company, investment]
---

# Salespush

**Overview:**
Salespush is a $13B investment vehicle...
```

## 🔗 How the System Works

### 1. **Note Nodes**
- Each `.md` file becomes a **Note node** in the knowledge graph
- The note's content is stored in the `content` field
- The note's label is the filename (without extension)

### 2. **Entity Nodes**
- **Person nodes** and **Company nodes** are created from LLM-extracted relationships
- These represent the actual entities mentioned in your notes
- They are separate from Note nodes

### 3. **Metadata Inheritance**
- **Metadata from notes is pulled into corresponding entity nodes**
- The system matches note filenames to entity names (case-insensitive)
- Example: `Josh Klein.md` → `Josh Klen` Person node gets the metadata

### 4. **Linking in Metadata**
- **Use `[[double brackets]]` for internal links** in metadata
- These create relationships between Note nodes in the graph
- Example: `company: "[[Salespush]]"` creates a link to `Salespush.md`

## ⚠️ Important Notes

### **Entity Creation Limitation**
> **An entity in the metadata region is not created in the knowledge graph yet.**
> 
> The system only creates Person/Company nodes from relationships extracted by the LLM from note content, not from metadata fields.

### **Linking Strategy**
> **If you use a link in the metadata, it is linked to the target Note node in the graph.**
> 
> This creates a connection between the current note and the linked note, but doesn't create entity nodes.

## 🎯 Best Practices

### 1. **For Person Notes**
```yaml
---
name: "Full Name"
title: "Job Title"
company: "[[Company Name]]"  # Link to company note
email: "email@example.com"
phone: "+1-555-0123"
location: "City, State"
tags: [person, role, industry]
---

# Full Name

**Summary:**
Write a brief summary of the person...

**Background:**
- Education
- Experience
- Key relationships

**Current Role:**
- Position
- Responsibilities
- Key projects
```

### 2. **For Company Notes**
```yaml
---
name: "Company Name"
industry: "Industry Type"
founded: 2020
headquarters: "City, State"
website: "https://company.com"
ceo: "[[CEO Name]]"  # Link to person note
tags: [company, industry, size]
---

# Company Name

**Overview:**
Brief company description...

**Key People:**
- [[Person 1]] - Role
- [[Person 2]] - Role

**Key Relationships:**
- Partners with [[Other Company]]
- Competes with [[Competitor]]
```

### 3. **For Meeting Notes**
```yaml
---
date: 2024-01-15
attendees: 
  - "[[Person 1]]"
  - "[[Person 2]]"
  - "[[Company Name]]"
tags: [meeting, project, date]
---

# Meeting Title

**Date:** January 15, 2024
**Attendees:** [[Person 1]], [[Person 2]], [[Company Name]]

**Agenda:**
1. Topic 1
2. Topic 2

**Action Items:**
- [ ] Task 1 - [[Person 1]]
- [ ] Task 2 - [[Person 2]]
```

## 🔄 Processing Pipeline

When you save a note, the system:

1. **Extracts relationships** using AI from the note content
2. **Creates/updates Person/Company nodes** based on extracted relationships
3. **Pulls metadata** from the note into the corresponding entity node
4. **Creates Note-to-Note links** from `[[brackets]]` in metadata
5. **Updates the knowledge graph** with all new information

## 📊 Viewing Your Knowledge Graph

Once processed, you can:

- **View the graph** in GraphXR at `http://localhost:7001/kuzudb/kuzu_db`
- **Query relationships** using Cypher queries
- **See metadata** attached to Person/Company nodes
- **Explore connections** between notes and entities

## 🚀 Getting Started

1. **Create your folder structure** (People/, Companies/, etc.)
2. **Write notes** following the naming convention
3. **Add metadata** using YAML frontmatter
4. **Use `[[links]]`** to connect related notes
5. **Start the monitoring system** to process your vault
6. **View your knowledge graph** in GraphXR

## 💡 Tips

- **Be consistent** with naming conventions
- **Use descriptive metadata** fields
- **Link related notes** using `[[brackets]]`
- **Keep metadata up to date** as information changes
- **Use tags** for additional categorization
- **Write clear summaries** in note content for better AI extraction

---

*This system transforms your Obsidian vault into an intelligent knowledge graph, making connections and insights visible that might otherwise remain hidden in individual notes.*
