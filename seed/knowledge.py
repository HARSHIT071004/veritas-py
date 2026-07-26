from app.data.models import KnowledgeDocument
from app.mcp.resources.knowledge import KnowledgeResource


def seed_knowledge_base(knowledge: KnowledgeResource):
    docs = [
        KnowledgeDocument(
            id="who-vaccines-1",
            title="WHO: Vaccines and immunization",
            content="Vaccines are safe and effective. All approved vaccines undergo rigorous testing through multiple phases of clinical trials before approval. Serious side effects are extremely rare. Vaccines train the immune system to recognize and fight pathogens.",
            source="World Health Organization",
            source_tier=1,
            url="https://www.who.int/health-topics/vaccines-and-immunization"
        ),
        KnowledgeDocument(
            id="who-covid-1",
            title="WHO: COVID-19 Myths and Facts",
            content="COVID-19 vaccines do not contain microchips. They cannot make you magnetic. They do not alter DNA. mRNA vaccines work by teaching cells how to make a protein that triggers an immune response, not by changing human DNA.",
            source="World Health Organization",
            source_tier=1,
            url="https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public/myth-busters"
        ),
        KnowledgeDocument(
            id="cdc-vitamins-1",
            title="CDC: Dietary Supplements",
            content="There is no evidence that high-dose vitamin C prevents or cures COVID-19. While vitamin C supports immune function, clinical trials have not shown it prevents infection. A balanced diet is the best source of vitamins and minerals.",
            source="Centers for Disease Control and Prevention",
            source_tier=1,
            url="https://www.cdc.gov/nutrition/micronutrients/faqs.html"
        ),
        KnowledgeDocument(
            id="snopes-5g-1",
            title="Snopes: 5G and COVID-19",
            content="There is no connection between 5G wireless technology and COVID-19. The theory that 5G causes or spreads COVID-19 is false and has been debunked by health organizations worldwide. Viruses cannot travel on radio waves.",
            source="Snopes",
            source_tier=2,
            url="https://www.snopes.com/fact-check/5g-coronavirus/"
        ),
        KnowledgeDocument(
            id="reuters-climate-1",
            title="Reuters Fact Check: Climate Change",
            content="Scientific consensus confirms that Earth's climate is warming due to human activities, primarily greenhouse gas emissions. Claims that climate change is a hoax or natural cycle are not supported by scientific evidence.",
            source="Reuters Fact Check",
            source_tier=2,
            url="https://www.reuters.com/fact-check"
        ),
        KnowledgeDocument(
            id="pubmed-vitamind-1",
            title="PubMed: Vitamin D and Respiratory Infections",
            content="Vitamin D supplementation may reduce risk of acute respiratory infections, but evidence is not conclusive for COVID-19 prevention. Randomized controlled trials show mixed results. Vitamin D is not a replacement for vaccination.",
            source="PubMed",
            source_tier=3,
            url="https://pubmed.ncbi.nlm.nih.gov/"
        ),
        KnowledgeDocument(
            id="who-antibiotics-1",
            title="WHO: Antibiotic Resistance",
            content="Antibiotics do not work against viruses. COVID-19 is caused by a virus, not bacteria. Taking antibiotics for viral infections contributes to antimicrobial resistance. Never self-prescribe antibiotics for viral illnesses.",
            source="World Health Organization",
            source_tier=1,
            url="https://www.who.int/news-room/fact-sheets/detail/antimicrobial-resistance"
        ),
        KnowledgeDocument(
            id="snopes-miracle-cure-1",
            title="Snopes: Miracle Cure Claims",
            content="Claims of 'miracle cures' that are suppressed by 'big pharma' are a common misinformation pattern. Legitimate medical breakthroughs are published in peer-reviewed journals and reviewed by regulatory bodies like the FDA and EMA.",
            source="Snopes",
            source_tier=2,
            url="https://www.snopes.com/fact-check/miracle-cure/"
        ),
        KnowledgeDocument(
            id="cdc-flu-1",
            title="CDC: Influenza Vaccine Facts",
            content="The flu vaccine cannot give you the flu. Flu vaccines contain inactivated viruses or single proteins, not live viruses. It takes about two weeks for protection to develop after vaccination. Annual vaccination is recommended.",
            source="Centers for Disease Control and Prevention",
            source_tier=1,
            url="https://www.cdc.gov/flu/prevent/keyfacts.htm"
        ),
        KnowledgeDocument(
            id="reuters-election-1",
            title="Reuters Fact Check: Election Fraud",
            content="Claims of widespread election fraud in US elections have been investigated and found to be unsubstantiated by courts, election officials, and audits. Voter fraud occurs at extremely low rates (0.0001% or less of votes cast).",
            source="Reuters Fact Check",
            source_tier=2,
            url="https://www.reuters.com/fact-check/elections"
        ),
        KnowledgeDocument(
            id="who-masks-1",
            title="WHO: Mask Use",
            content="Masks are a key measure to suppress transmission of respiratory viruses. Medical masks protect others from the wearer. Respirators (N95) protect the wearer. Masks should be part of a comprehensive strategy including vaccination and physical distancing.",
            source="World Health Organization",
            source_tier=1,
            url="https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public/when-and-how-to-use-masks"
        ),
        KnowledgeDocument(
            id="snopes-detox-1",
            title="Snopes: Detox Diets and Cleanses",
            content="The human body has its own detoxification system (liver, kidneys, lungs). There is no scientific evidence that detox diets, juice cleanses, or colon cleanses remove toxins. Most 'detox' claims are not supported by medical evidence.",
            source="Snopes",
            source_tier=2,
            url="https://www.snopes.com/fact-check/detox-diets/"
        ),
        KnowledgeDocument(
            id="who-gmo-1",
            title="WHO: Genetically Modified Foods",
            content="Genetically modified (GM) foods currently available on the international market have passed safety assessments and are not likely to present risks to human health. No effects on human health have been shown from GM foods approved for sale.",
            source="World Health Organization",
            source_tier=1,
            url="https://www.who.int/health-topics/food-genetically-modified"
        ),
        KnowledgeDocument(
            id="pubmed-homeopathy-1",
            title="PubMed: Homeopathy Effectiveness",
            content="Systematic reviews of homeopathy trials have found no convincing evidence that homeopathy is effective beyond placebo for any medical condition. The principles of homeopathy are inconsistent with established scientific laws.",
            source="PubMed",
            source_tier=3,
            url="https://pubmed.ncbi.nlm.nih.gov/"
        ),
        KnowledgeDocument(
            id="reuters-health-1",
            title="Reuters Fact Check: Health Misinformation",
            content="Claims that medical authorities are hiding natural cures for profit follow a recurring pattern. These claims typically lack peer-reviewed evidence, rely on anecdotal testimonials, and misrepresent the motives of medical research institutions.",
            source="Reuters Fact Check",
            source_tier=2,
            url="https://www.reuters.com/fact-check/health"
        ),
    ]
    knowledge.add_documents(docs)
