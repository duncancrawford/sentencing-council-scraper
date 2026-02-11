from sentence_chat_product.etl.build_dataset import (
    build_offence_catalog_and_links,
    guideline_doc_from_offence_guideline,
)


def test_mapping_by_guideline_slug():
    guideline_docs = [
        guideline_doc_from_offence_guideline(
            {
                "offence_name": "Common assault",
                "url": "https://www.sentencingcouncil.org.uk/guidelines/common-assault/",
                "court_type": "both",
                "category": "Assault offences",
                "source_tab": "Offences",
                "sentencing_ranges": [],
            }
        )
    ]

    sentenceace = [
        {
            "offencename": "Criminal Justice Act 1988 s.39: Common assault",
            "offencecategory": "Assault offences",
            "provision": "Criminal Justice Act 1988 s.39",
            "guideline": "https://www.sentencingcouncil.org.uk/offences/crown-court/item/common-assault/",
            "hyperlink": "",
            "maximumsentencetype": "custody",
            "maximumsentenceamount": "6 months",
            "minimumsentence": "",
            "specifiedviolentoffence": "No",
            "specifiedsexualoffence": "No",
            "specifiedterroristoffence": "No",
            "listedoffence": "No",
            "schedule18Aoffence": "No",
            "schedule19za": "No",
            "ctanotification": "No",
            "shpo": "No",
            "disqualification": "No",
            "safeguarding1": "No",
            "safeguarding2": "No",
            "safeguarding3": "No",
            "safeguarding4": "No",
        }
    ]

    offences, links, primary_map, issues = build_offence_catalog_and_links(
        sentenceace_rows=sentenceace,
        guideline_docs=guideline_docs,
        fuzzy_threshold=90,
    )

    assert len(offences) == 1
    assert len(links) == 1
    assert not issues
    assert links[0]["match_method"] in {"guideline_slug", "name_slug"}
    assert links[0]["guideline_id"] in primary_map
