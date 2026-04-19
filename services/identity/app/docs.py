HEALTH_RESPONSES = {
    200: {
        "description": "Service health status",
        "content": {
            "application/json": {
                "example": {
                    "status": "ok",
                    "service": "identity",
                    "ldap_server": "ldap://ldap-server:1389",
                }
            }
        },
    }
}

STATS_RESPONSES = {
    200: {
        "description": "LDAP record statistics",
        "content": {
            "application/json": {
                "example": {
                    "total_in_ldap": 28473,
                    "with_email": 14210,
                    "without_email": 14263,
                }
            }
        },
    }
}

SYNC_FILE_RESPONSES = {
    200: {
        "description": "Background sync job accepted",
        "content": {
            "application/json": {
                "example": {"message": "Sync started. Check docker logs for progress."}
            }
        },
    }
}

LOOKUP_RESPONSES = {
    200: {
        "description": "Exact match or fuzzy-match suggestions",
        "content": {
            "application/json": {
                "examples": {
                    "exact_match": {
                        "summary": "Exact match found",
                        "value": {
                            "record": {
                                "username": "jzhang",
                                "name": "Jue Zhang",
                                "email": "jue.zhang@university.edu",
                                "org": "Carnegie Mellon University",
                            },
                            "similar_records": None,
                            "message": "Match found.",
                        },
                    },
                    "suggestions": {
                        "summary": "Fuzzy suggestions returned",
                        "value": {
                            "record": None,
                            "similar_records": [
                                {
                                    "name": "Jue Zhang",
                                    "email": "jue.zhang@university.edu",
                                    "org": "Carnegie Mellon University",
                                    "score": 57.14,
                                },
                                {
                                    "name": "Ethan Zhang",
                                    "email": "ethan.zhang@dtic.mil",
                                    "org": "DTIC",
                                    "score": 66.67,
                                },
                            ],
                            "message": "Suggestions provided.",
                        },
                    },
                }
            }
        },
    },
    500: {
        "description": "LDAP lookup error",
        "content": {
            "application/json": {
                "example": {"detail": "LDAP connection failed"}
            }
        },
    },
}
