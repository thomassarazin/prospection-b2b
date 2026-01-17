# Templates icebreakers par code NAF (fallback intelligent quand scraping échoue)
# Contexte mail : "Vous bossez sur [activite_principale]", "Que ce soit [operations_concretes], ça prend du temps...", "Vous valorisez [valeur_humaine]"
TEMPLATES_ICEBREAKER_NAF = {
    # CONSEIL EN RELATIONS PUBLIQUES & COMMUNICATION (7021Z)
    "7021Z": {
        "activite_principale": "les stratégies de communication de vos clients",
        "operations_concretes": "la rédaction des communiqués, les relances journalistes, la veille médias et les rapports de retombées",
        "valeur_humaine": "la réactivité",
        "description_entreprise": "Ce cabinet conseille ses clients en matière de relations publiques et communication, les accompagnant dans leur stratégie de visibilité médiatique."
    },

    # ACTIVITÉS DES AGENCES DE PUBLICITÉ (7311Z)
    "7311Z": {
        "activite_principale": "la création publicitaire pour vos clients",
        "operations_concretes": "les allers-retours de validation, la coordination entre équipes créatives et la gestion des achats d'espaces médias",
        "valeur_humaine": "la créativité",
        "description_entreprise": "Cette agence conçoit et déploie des campagnes publicitaires pour ses clients, de la création des supports à la diffusion sur les différents canaux."
    },

    # CONSEIL POUR LES AFFAIRES ET GESTION (7022Z)
    "7022Z": {
        "activite_principale": "l'accompagnement stratégique de vos clients",
        "operations_concretes": "la collecte et l'analyse de données, la production de livrables et la coordination des ateliers avec les équipes",
        "valeur_humaine": "la rigueur méthodologique",
        "description_entreprise": "Ce cabinet de conseil accompagne les entreprises dans leurs décisions stratégiques et l'optimisation de leur organisation."
    },

    # VENTE À DISTANCE SUR CATALOGUE GÉNÉRAL (4791A)
    "4791A": {
        "activite_principale": "la gestion d'un large catalogue de produits en ligne",
        "operations_concretes": "la coordination des stocks sur des centaines de références, la logistique des expéditions et la gestion des retours clients",
        "valeur_humaine": "la réactivité du service client",
        "description_entreprise": "Cette entreprise de vente à distance gère un catalogue généraliste avec de multiples catégories de produits, orchestrant à la fois les ventes en ligne et la logistique associée."
    },

    # VENTE À DISTANCE SUR CATALOGUE SPÉCIALISÉ (4791B)
    "4791B": {
        "activite_principale": "la vente en ligne de vos produits",
        "operations_concretes": "la mise à jour du catalogue, le traitement manuel des commandes et la gestion du SAV client",
        "valeur_humaine": "la satisfaction client",
        "description_entreprise": "Cette entreprise commercialise des produits à distance via son catalogue en ligne, gérant l'ensemble du parcours d'achat digital."
    }
}

# Templates automatisations par code NAF (fallback si Groq échoue)
# Format : Liste markdown de 3 automatisations 100% réalisables (Make/Zapier ou Python+API)
TEMPLATES_AUTOMATIONS_NAF = {
    # CONSEIL EN RELATIONS PUBLIQUES & COMMUNICATION (7021Z)
    "7021Z": """- Envoyer automatiquement un rapport mensuel à chaque client le 1er du mois avec les retombées presse compilées depuis votre tableau de suivi
- Recevoir chaque matin par email un digest des actualités liées aux secteurs de vos clients, filtrées depuis vos flux RSS habituels
- Créer automatiquement une tâche dans votre outil de gestion de projet dès qu'un nouveau communiqué est ajouté au drive, et assigner la personne responsable du suivi""",

    # ACTIVITÉS DES AGENCES DE PUBLICITÉ (7311Z)
    "7311Z": """- Récupérer automatiquement les performances de vos campagnes Meta et Google Ads chaque lundi et compiler un rapport envoyé par email à chaque client
- Envoyer une notification à toute l'équipe concernée dès qu'un fichier est ajouté au dossier de validation client, avec un lien direct vers le fichier
- Recevoir une alerte email dès qu'une campagne atteint 80% de son budget, avec le montant restant et la date de fin prévue au rythme actuel""",

    # CONSEIL POUR LES AFFAIRES ET GESTION (7022Z)
    "7022Z": """- Ajouter automatiquement les réponses des questionnaires clients dans un Google Sheets avec graphiques pré-configurés qui se mettent à jour en temps réel
- Envoyer automatiquement les invitations d'atelier une semaine avant la date calendrier, puis une relance la veille avec le lien de visio et les documents
- Recevoir une notification 2 semaines avant chaque deadline de plan d'action notée dans votre tableau de suivi, avec la liste des actions en retard""",

# VENTE À DISTANCE SUR CATALOGUE GÉNÉRAL (4791A)
    "4791A": """- Trier automatiquement les demandes SAV par type (livraison, retour, question produit) et les assigner à la bonne équipe avec toutes les infos de commande déjà chargées.
- Recevoir une alerte quand un fournisseur modifie ses tarifs ou son stock, pour mettre à jour automatiquement les fiches produits correspondantes.
- Générer chaque semaine un rapport qui analyse les ventes croisées entre catégories, pour créer automatiquement des offres groupées ('bundles') sur le site.""",

    # VENTE À DISTANCE SUR CATALOGUE SPÉCIALISÉ (4791B)
    "4791B": """- Envoyer automatiquement un email de relance 24h après un abandon de panier avec les produits laissés, puis un second email à J+3 avec un code promo si pas de commande
- Recevoir une alerte dès qu'un produit passe sous votre seuil de stock minimum défini, avec le nombre de ventes des 30 derniers jours pour anticiper la commande
- Ajouter automatiquement chaque nouveau message client dans un tableau de suivi avec horodatage, et créer une tâche si pas de réponse sous 24h"""
}
