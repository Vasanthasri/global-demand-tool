"""
Global Demand Analysis Tool
Domain Map: keywords → domain → sub-domains → signals → sources
"""

DOMAIN_MAP = {
    "Technology": {
        "keywords": [
            "ai", "artificial intelligence", "machine learning", "deep learning",
            "software", "saas", "app", "application", "cloud", "aws", "azure",
            "gcp", "devops", "api", "web development", "mobile", "ios", "android",
            "cybersecurity", "blockchain", "crypto", "web3", "iot", "internet of things",
            "quantum", "ar", "vr", "metaverse", "robotics", "automation", "nlp",
            "llm", "gpt", "semiconductor", "chip", "hardware", "data science",
            "analytics", "database", "sql", "nosql", "microservices", "kubernetes",
            "docker", "react", "node", "python", "java", "rust", "golang", "sap",
            "erp", "crm", "tech", "digital", "platform", "open source", "developer",
            "programming", "coding", "infrastructure", "network", "server"
        ],
        "sub_domains": {
            "Artificial Intelligence": {
                "keywords": ["ai", "artificial intelligence", "machine learning", "deep learning", "llm", "gpt", "nlp", "neural network"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/MachineLearning", "reddit.com/r/artificial", "news.ycombinator.com", "stackoverflow.com"],
                    "Buyer Signal": ["linkedin.com/jobs", "glassdoor.com", "indeed.com"],
                    "Competitor Signal": ["crunchbase.com", "g2.com/categories/ai-platforms", "capterra.com"],
                    "Timing Signal": ["arxiv.org", "paperswithcode.com", "aiindex.stanford.edu"],
                    "Validation Signal": ["producthunt.com", "github.com/trending"],
                    "Market Data": ["statista.com", "gartner.com", "idc.com", "mckinsey.com/ai"]
                }
            },
            "Cloud Computing": {
                "keywords": ["cloud", "aws", "azure", "gcp", "saas", "paas", "iaas", "serverless"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/aws", "reddit.com/r/devops", "stackoverflow.com"],
                    "Buyer Signal": ["linkedin.com/jobs", "flexera.com/cloud"],
                    "Competitor Signal": ["srgresearch.com", "canalys.com/cloud", "g2.com"],
                    "Market Data": ["synergyrp.com", "idc.com", "gartner.com"]
                }
            },
            "Cybersecurity": {
                "keywords": ["cybersecurity", "security", "hacking", "breach", "ransomware", "zero day", "siem", "firewall"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/netsec", "bleepingcomputer.com", "krebsonsecurity.com"],
                    "Buyer Signal": ["linkedin.com/jobs", "darkreading.com"],
                    "Competitor Signal": ["g2.com/categories/endpoint-security", "gartner.com"],
                    "Timing Signal": ["nvd.nist.gov", "cisa.gov", "exploit-db.com"],
                    "Market Data": ["verizon.com/dbir", "ibm.com/security/data-breach"]
                }
            },
            "Web Development": {
                "keywords": ["web development", "react", "vue", "angular", "javascript", "typescript", "frontend", "backend", "fullstack"],
                "sources": {
                    "Pain Signal": ["stackoverflow.com", "reddit.com/r/webdev", "news.ycombinator.com"],
                    "Buyer Signal": ["linkedin.com/jobs", "indeed.com"],
                    "Competitor Signal": ["stateofjs.com", "builtwith.com", "w3techs.com"],
                    "Market Data": ["jetbrains.com/lp/devecosystem", "github.com/octoverse"]
                }
            },
            "SAP & Enterprise Software": {
                "keywords": ["sap", "erp", "oracle", "salesforce", "enterprise software", "crm", "hana"],
                "sources": {
                    "Pain Signal": [
                        "reddit.com/r/SAP",
                        "sapinsider.org",
                        "g2.com",
                        "community.sap.com",        # ← new
                        "reddit.com/r/ERPsystems",  # ← new
                    ],
                    "Buyer Signal": [
                        "linkedin.com/jobs",
                        "gartner.com/magic-quadrant",
                        "glassdoor.com",            # ← new
                    ],
                    "Competitor Signal": [
                        "g2.com/categories/erp",
                        "capterra.com",
                        "trustradius.com",
                        "softwareadvice.com/erp",   # ← new
                        "peerspot.com",             # ← new
                    ],
                    "Timing Signal": [             # ← new signal type
                        "sapcentral.com",
                        "dsag.de",
                    ],
                    "Validation Signal": [         # ← new signal type
                        "blogs.sap.com",
                        "news.sap.com",
                    ],
                    "Market Data": [
                        "gartner.com",
                        "forrester.com",
                        "idc.com",
                        "statista.com",             # ← new
                        "marketsandmarkets.com",    # ← new
                    ]
                }
            },
            "Blockchain & Web3": {
                "keywords": ["blockchain", "crypto", "web3", "nft", "defi", "ethereum", "bitcoin", "dao"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/ethereum", "reddit.com/r/CryptoCurrency"],
                    "Buyer Signal": ["linkedin.com/jobs", "crunchbase.com"],
                    "Competitor Signal": ["defillama.com", "dappradar.com", "coinmarketcap.com"],
                    "Market Data": ["messari.io", "glassnode.com", "chainalysis.com"]
                }
            }
        }
    },

    "Health & Life Sciences": {
        "keywords": [
            "health", "healthcare", "medical", "medicine", "pharma", "pharmaceutical",
            "drug", "clinical", "hospital", "patient", "doctor", "nurse", "surgery",
            "biotech", "genomics", "dna", "rna", "cancer", "diabetes", "mental health",
            "therapy", "vaccine", "diagnosis", "treatment", "device", "imaging",
            "telemedicine", "telehealth", "wearable", "fitness", "wellness", "nutrition",
            "elder care", "aging", "insurance health", "fda", "ema", "clinical trial"
        ],
        "sub_domains": {
            "Digital Health & Telemedicine": {
                "keywords": ["telemedicine", "telehealth", "digital health", "health app", "wearable"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/medicine", "reddit.com/r/health"],
                    "Buyer Signal": ["linkedin.com/jobs", "clinicaltrials.gov"],
                    "Competitor Signal": ["crunchbase.com", "g2.com/categories/telemedicine"],
                    "Market Data": ["healthdata.org", "who.int", "kff.org"]
                }
            },
            "Pharmaceuticals": {
                "keywords": ["pharma", "pharmaceutical", "drug", "fda", "clinical trial", "vaccine"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/medicine", "fiercepharma.com"],
                    "Competitor Signal": ["evaluate.com/pharma", "iqvia.com"],
                    "Timing Signal": ["fda.gov", "ema.europa.eu", "clinicaltrials.gov"],
                    "Market Data": ["iqvia.com", "phrma.org", "statista.com"]
                }
            },
            "Mental Health": {
                "keywords": ["mental health", "therapy", "anxiety", "depression", "psychology", "psychiatry"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/mentalhealth", "reddit.com/r/therapy"],
                    "Buyer Signal": ["linkedin.com/jobs", "psychologytoday.com"],
                    "Market Data": ["nimh.nih.gov", "who.int", "samhsa.gov"]
                }
            },
            "Biotech & Genomics": {
                "keywords": ["biotech", "genomics", "gene", "crispr", "protein", "bioinformatics"],
                "sources": {
                    "Competitor Signal": ["crunchbase.com", "bio.org"],
                    "Timing Signal": ["nature.com/biotech", "genome.gov", "ncbi.nlm.nih.gov"],
                    "Market Data": ["genengnews.com", "fiercebiotech.com"]
                }
            }
        }
    },

    "Finance & Economy": {
        "keywords": [
            "finance", "financial", "banking", "bank", "investment", "investing",
            "stock", "market", "trading", "fintech", "payment", "insurance",
            "wealth", "crypto", "forex", "mortgage", "loan", "credit", "debit",
            "wallet", "neobank", "lending", "vc", "venture capital", "private equity",
            "ipo", "startup funding", "economy", "gdp", "inflation", "interest rate",
            "tax", "accounting", "audit", "compliance", "risk", "hedge fund"
        ],
        "sub_domains": {
            "Fintech": {
                "keywords": ["fintech", "neobank", "digital payment", "wallet", "buy now pay later", "bnpl"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/personalfinance", "reddit.com/r/fintech"],
                    "Buyer Signal": ["linkedin.com/jobs", "crunchbase.com"],
                    "Competitor Signal": ["cbinsights.com/fintech", "finovate.com", "g2.com"],
                    "Market Data": ["fintechglobal.com", "statista.com", "imf.org"]
                }
            },
            "Investment & VC": {
                "keywords": ["venture capital", "vc", "startup funding", "seed", "series a", "private equity", "ipo"],
                "sources": {
                    "Competitor Signal": ["crunchbase.com", "pitchbook.com", "dealroom.co"],
                    "Validation Signal": ["angel.co", "producthunt.com"],
                    "Market Data": ["nvca.org", "cbinsights.com", "preqin.com"]
                }
            },
            "Banking": {
                "keywords": ["bank", "banking", "credit union", "mortgage", "loan", "interest rate"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/personalfinance", "reddit.com/r/Banking"],
                    "Timing Signal": ["federalreserve.gov", "bis.org", "ecb.europa.eu"],
                    "Market Data": ["thebanker.com", "bankersalmanac.com", "fred.stlouisfed.org"]
                }
            }
        }
    },

    "Education": {
        "keywords": [
            "education", "learning", "school", "university", "college", "course",
            "edtech", "online learning", "mooc", "training", "skill", "certification",
            "tutoring", "teaching", "curriculum", "student", "teacher", "classroom",
            "bootcamp", "vocational", "degree", "exam", "assessment", "literacy",
            "e-learning", "lms", "coursera", "udemy", "khan academy"
        ],
        "sub_domains": {
            "EdTech & Online Learning": {
                "keywords": ["edtech", "online learning", "mooc", "lms", "e-learning", "coursera", "udemy"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/learnprogramming", "reddit.com/r/edtech"],
                    "Buyer Signal": ["linkedin.com/jobs", "classcentral.com"],
                    "Competitor Signal": ["holoniq.com", "g2.com/categories/learning-management-systems"],
                    "Market Data": ["edsurge.com", "statista.com", "holoniq.com"]
                }
            },
            "Higher Education": {
                "keywords": ["university", "college", "degree", "higher education", "research"],
                "sources": {
                    "Market Data": ["topuniversities.com", "timeshighereducation.com", "nces.ed.gov"]
                }
            }
        }
    },

    "Retail & Consumer Goods": {
        "keywords": [
            "retail", "ecommerce", "e-commerce", "shopping", "consumer", "product",
            "brand", "store", "marketplace", "amazon", "shopify", "d2c", "direct to consumer",
            "fmcg", "cpg", "luxury", "fashion", "apparel", "beauty", "cosmetics",
            "personal care", "home goods", "furniture", "electronics", "grocery",
            "subscription", "membership", "loyalty", "customer", "buyer", "purchase"
        ],
        "sub_domains": {
            "E-Commerce": {
                "keywords": ["ecommerce", "e-commerce", "shopify", "amazon", "marketplace", "online store"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/ecommerce", "reddit.com/r/fulfillment"],
                    "Buyer Signal": ["google.com/trends", "amazon.com/best-sellers"],
                    "Competitor Signal": ["marketplacepulse.com", "similarweb.com"],
                    "Market Data": ["emarketer.com", "digitalcommerce360.com", "shopify.com/research"]
                }
            },
            "FMCG & CPG": {
                "keywords": ["fmcg", "cpg", "consumer goods", "grocery", "food brand", "beverage"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/GroceryStores"],
                    "Competitor Signal": ["nielseniq.com", "circana.com", "iriworldwide.com"],
                    "Market Data": ["euromonitor.com", "mintel.com", "kantar.com"]
                }
            },
            "Luxury Goods": {
                "keywords": ["luxury", "premium", "high end", "designer", "louis vuitton", "gucci"],
                "sources": {
                    "Competitor Signal": ["bain.com/luxury", "lyst.com/insights"],
                    "Market Data": ["businessoffashion.com", "euromonitor.com"]
                }
            }
        }
    },

    "Media & Entertainment": {
        "keywords": [
            "media", "entertainment", "streaming", "video", "music", "gaming", "game",
            "movie", "film", "tv", "television", "podcast", "content", "creator",
            "youtube", "netflix", "spotify", "twitch", "esports", "animation",
            "publishing", "news", "journalism", "social media", "influencer",
            "vr gaming", "mobile game", "console", "subscription media"
        ],
        "sub_domains": {
            "Gaming": {
                "keywords": ["gaming", "game", "esports", "mobile game", "console", "steam", "twitch"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/gaming", "reddit.com/r/gamedev"],
                    "Buyer Signal": ["steamspy.com", "vgchartz.com"],
                    "Competitor Signal": ["newzoo.com", "gamesindustry.biz"],
                    "Market Data": ["newzoo.com", "superdataresearch.com", "statista.com"]
                }
            },
            "Streaming & OTT": {
                "keywords": ["streaming", "netflix", "disney", "hulu", "ott", "video on demand"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/cordcutters"],
                    "Competitor Signal": ["flixpatrol.com", "parrotanalytics.com", "justwatch.com"],
                    "Market Data": ["ampere-analysis.com", "whip-media.com", "statista.com"]
                }
            },
            "Music": {
                "keywords": ["music", "spotify", "artist", "label", "concert", "album", "streaming music"],
                "sources": {
                    "Competitor Signal": ["charts.spotify.com", "kworb.net"],
                    "Market Data": ["ifpi.org", "riaa.com", "billboard.com"]
                }
            }
        }
    },

    "Transportation & Mobility": {
        "keywords": [
            "transport", "transportation", "mobility", "vehicle", "car", "automobile",
            "electric vehicle", "ev", "autonomous", "self driving", "aviation", "airline",
            "shipping", "logistics", "supply chain", "freight", "delivery", "last mile",
            "ride sharing", "uber", "lyft", "scooter", "bike", "public transit",
            "train", "rail", "bus", "port", "cargo", "drone delivery"
        ],
        "sub_domains": {
            "Electric Vehicles": {
                "keywords": ["electric vehicle", "ev", "tesla", "battery", "charging station", "bev"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/electricvehicles"],
                    "Competitor Signal": ["ev-volumes.com", "insideevs.com"],
                    "Timing Signal": ["iea.org/ev", "regulations.gov"],
                    "Market Data": ["iea.org", "bnef.com", "wardsauto.com"]
                }
            },
            "Logistics & Supply Chain": {
                "keywords": ["logistics", "supply chain", "freight", "shipping", "warehouse", "last mile"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/logistics", "supplychaindive.com"],
                    "Competitor Signal": ["freightos.com", "drewry.co.uk"],
                    "Market Data": ["freightwave.com", "logisticsmgmt.com", "imo.org"]
                }
            }
        }
    },

    "Environment & Sustainability": {
        "keywords": [
            "environment", "sustainability", "climate", "green", "renewable", "solar",
            "wind", "energy", "carbon", "emission", "esg", "clean tech", "cleantech",
            "recycling", "waste", "water treatment", "conservation", "biodiversity",
            "net zero", "carbon neutral", "offset", "green hydrogen", "battery storage",
            "circular economy", "sustainable", "eco", "environmental"
        ],
        "sub_domains": {
            "Renewable Energy": {
                "keywords": ["renewable", "solar", "wind", "green energy", "clean energy", "hydrogen"],
                "sources": {
                    "Timing Signal": ["irena.org", "iea.org/renewables", "ember-climate.org"],
                    "Market Data": ["renewableenergyworld.com", "pv-tech.org", "windpowermonthly.com"]
                }
            },
            "ESG & Climate Tech": {
                "keywords": ["esg", "climate tech", "carbon offset", "net zero", "sustainability"],
                "sources": {
                    "Competitor Signal": ["crunchbase.com", "climatewire.net"],
                    "Timing Signal": ["ipcc.ch", "cdp.net", "climateactiontracker.org"],
                    "Market Data": ["msci.com/esg", "sustainalytics.com", "greenbiz.com"]
                }
            }
        }
    },

    "Agriculture & Food Tech": {
        "keywords": [
            "agriculture", "farming", "agtech", "crop", "food", "food tech", "agri",
            "precision farming", "vertical farming", "hydroponics", "alternative protein",
            "plant based", "lab grown", "cultivated meat", "food supply", "seed",
            "fertilizer", "pesticide", "irrigation", "livestock", "dairy", "aquaculture"
        ],
        "sub_domains": {
            "AgTech": {
                "keywords": ["agtech", "precision farming", "smart farming", "drone agriculture"],
                "sources": {
                    "Competitor Signal": ["agfunder.com", "crunchbase.com"],
                    "Market Data": ["agdaily.com", "precisionag.com", "agfunder.com"]
                }
            },
            "Alternative Proteins": {
                "keywords": ["alternative protein", "plant based", "lab grown meat", "cultivated", "vegan food"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/PlantBasedDiet"],
                    "Competitor Signal": ["gfi.org", "vegconomist.com"],
                    "Market Data": ["gfi.org", "foodnavigator.com", "fooddive.com"]
                }
            }
        }
    },

    "Marketing & Advertising": {
        "keywords": [
            "marketing", "advertising", "seo", "sem", "ppc", "social media marketing",
            "content marketing", "email marketing", "influencer", "brand", "campaign",
            "digital marketing", "growth hacking", "conversion", "funnel", "crm",
            "hubspot", "mailchimp", "google ads", "facebook ads", "programmatic",
            "marketing automation", "lead generation", "demand generation", "pr"
        ],
        "sub_domains": {
            "Digital Marketing": {
                "keywords": ["digital marketing", "seo", "sem", "ppc", "google ads", "content marketing"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/digital_marketing", "reddit.com/r/SEO"],
                    "Competitor Signal": ["semrush.com", "ahrefs.com", "similarweb.com"],
                    "Market Data": ["emarketer.com", "hubspot.com/marketing-statistics", "iab.com"]
                }
            },
            "Advertising Market": {
                "keywords": ["advertising", "ad spend", "programmatic", "brand campaign"],
                "sources": {
                    "Market Data": ["warc.com", "groupm.com", "adage.com", "statista.com"]
                }
            }
        }
    },

    "Real Estate & Construction": {
        "keywords": [
            "real estate", "property", "housing", "construction", "building", "commercial",
            "residential", "office", "retail space", "reit", "mortgage", "landlord",
            "tenant", "rent", "lease", "smart building", "smart city", "proptech",
            "architecture", "urban", "infrastructure", "bridge", "highway"
        ],
        "sub_domains": {
            "Proptech": {
                "keywords": ["proptech", "real estate tech", "smart building", "property management software"],
                "sources": {
                    "Competitor Signal": ["crunchbase.com", "g2.com"],
                    "Market Data": ["jll.com/research", "cbre.com/research", "zillow.com/research"]
                }
            },
            "Construction": {
                "keywords": ["construction", "building", "contractor", "infrastructure"],
                "sources": {
                    "Market Data": ["construction.com", "enr.com", "constructiondive.com"]
                }
            }
        }
    },

    "Manufacturing & Industry": {
        "keywords": [
            "manufacturing", "industry", "industrial", "factory", "production", "steel",
            "chemical", "aerospace", "automotive manufacturing", "electronics manufacturing",
            "3d printing", "additive manufacturing", "cnc", "iot manufacturing", "industry 4.0",
            "supply chain manufacturing", "quality control", "lean", "six sigma"
        ],
        "sub_domains": {
            "Industry 4.0": {
                "keywords": ["industry 4.0", "smart factory", "iot manufacturing", "digital twin"],
                "sources": {
                    "Competitor Signal": ["crunchbase.com", "automationworld.com"],
                    "Market Data": ["industryweek.com", "manufacturing.net", "ism.world"]
                }
            },
            "Aerospace & Defense": {
                "keywords": ["aerospace", "defense", "military", "aviation manufacturing", "space"],
                "sources": {
                    "Timing Signal": ["sipri.org", "aia-aerospace.org"],
                    "Market Data": ["aviationweek.com", "flightglobal.com", "defensenews.com"]
                }
            }
        }
    },

    "Government & Public Services": {
        "keywords": [
            "government", "public sector", "policy", "regulation", "law", "legal",
            "compliance", "defense", "military", "public health", "social welfare",
            "election", "democracy", "governance", "municipality", "federal", "state",
            "smart city", "e-government", "civic tech", "public safety"
        ],
        "sub_domains": {
            "Civic Tech": {
                "keywords": ["civic tech", "e-government", "smart city", "open data"],
                "sources": {
                    "Market Data": ["brookings.edu", "oecd.org/gov", "data.gov"]
                }
            },
            "Defense": {
                "keywords": ["defense", "military", "security", "intelligence"],
                "sources": {
                    "Market Data": ["sipri.org", "defensenews.com", "janes.com"]
                }
            }
        }
    },

    "Tourism & Hospitality": {
        "keywords": [
            "tourism", "travel", "hotel", "hospitality", "restaurant", "food service",
            "airbnb", "booking", "airline travel", "vacation", "cruise", "resort",
            "experience", "event", "conference", "wedding", "catering", "bar", "cafe"
        ],
        "sub_domains": {
            "Travel Tech": {
                "keywords": ["travel tech", "booking platform", "ota", "online travel"],
                "sources": {
                    "Competitor Signal": ["phocuswire.com", "skift.com"],
                    "Market Data": ["unwto.org", "wttc.org", "str.com"]
                }
            },
            "Food Service": {
                "keywords": ["restaurant", "food service", "catering", "quick service", "fast food"],
                "sources": {
                    "Market Data": ["nra.org", "technomic.com", "datassential.com"]
                }
            }
        }
    },

    "Social & Human Services": {
        "keywords": [
            "social", "ngo", "nonprofit", "charity", "welfare", "poverty", "inequality",
            "immigration", "refugee", "gender equality", "diversity", "inclusion",
            "labor", "employment", "job", "workforce", "hr", "human resources",
            "community", "volunteer", "social impact", "philanthropy"
        ],
        "sub_domains": {
            "HR & Workforce": {
                "keywords": ["hr", "human resources", "workforce", "recruitment", "talent", "hiring"],
                "sources": {
                    "Pain Signal": ["reddit.com/r/humanresources", "reddit.com/r/jobs"],
                    "Competitor Signal": ["g2.com/categories/hr", "capterra.com"],
                    "Market Data": ["shrm.org", "linkedin.com/pulse/trends", "glassdoor.com/research"]
                }
            },
            "Social Impact": {
                "keywords": ["ngo", "nonprofit", "social impact", "philanthropy", "charity"],
                "sources": {
                    "Market Data": ["worldbank.org/poverty", "undp.org", "oxfam.org/research"]
                }
            }
        }
    },

    "Science & Research": {
        "keywords": [
            "science", "research", "laboratory", "experiment", "study", "paper",
            "journal", "academic", "university research", "physics", "chemistry",
            "biology", "materials science", "nanotechnology", "space science",
            "climate science", "neuroscience", "data research"
        ],
        "sub_domains": {
            "Life Sciences Research": {
                "keywords": ["biology", "neuroscience", "genomics research", "clinical research"],
                "sources": {
                    "Market Data": ["nature.com", "pubmed.ncbi.nlm.nih.gov", "researchgate.net"]
                }
            },
            "Physical Sciences": {
                "keywords": ["physics", "chemistry", "materials", "quantum", "nanotechnology"],
                "sources": {
                    "Market Data": ["nature.com", "arxiv.org", "aps.org", "rsc.org"]
                }
            }
        }
    }
}

# Demand signal descriptions for report display
SIGNAL_DESCRIPTIONS = {
    "Pain Signal": "Is the problem real & recurring? Evidence of current friction, frequency, and complexity.",
    "Buyer Signal": "Is the right person ready to act? Awareness, urgency, and decision authority.",
    "Deal Signal": "Can this actually close? Budget availability, switching costs, and ROI visibility.",
    "Competitor Signal": "Does existing competition prove the market? Proxy revenue and incumbent gaps.",
    "Behaviour Signal": "Are people already trying to solve this? Workarounds, communities, content consumption.",
    "Timing Signal": "Is the window opening now? Regulatory shifts, tech enablement, macro changes.",
    "Expansion Signal": "Will demand compound over time? Network effects, word-of-mouth, adjacent expansion.",
    "Validation Signal": "Have real buyers confirmed demand with action? Pre-sales, waitlists, inbound pull.",
    "Market Data": "Quantitative market size, growth rates, and forecasts."
}
