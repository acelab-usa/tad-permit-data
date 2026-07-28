"""Registers every jurisdiction the pipeline knows how to ingest.

To onboard a new jurisdiction, add one entry to SOURCES below -- either a
SocrataAPISource or a PDFLedgerSource. Nothing else in the pipeline needs to
change.

A SocrataAPISource needs a FieldMapping (see sources/field_mapping.py) that
declares which raw field(s) hold each piece of PermitSchemaV2 -- most cities
need nothing more than that (see `seattle` below). Only reach for a custom
`scope_builder` (see `nyc` below) when a field genuinely can't be expressed
as "rename this column" or "try these columns in order."
"""
from sources.arcgis import ArcGISFeatureSource
from sources.field_mapping import FieldMapping, build_mapper
from sources.pdf_ledger import PDFLedgerSource
from sources.socrata import SocrataAPISource

# Candidate point-geometry field names to check per dataset, in addition to
# the plain latitude/longitude-ish fields geo.py always tries first. Not
# verified against live API responses -- see geo.py's module docstring.
_GEO_POINT_FIELDS = ("location", "geocoded_location", "the_geom")


CHICAGO_MAPPING = FieldMapping(
    jurisdiction="chicago",
    source_url="https://data.cityofchicago.org/resource/ydr8-56us.json",
    permit_id_field="permit_",
    address_fields=("street_number", "street_direction", "street_name", "suffix"),
    date_fields=("issue_date",),
    owner_name_fields=("contact_1_name",),
    contractor_name_fields=("contact_2_name",),
    permit_type_fields=("permit_type",),
    valuation_field="reported_cost",
    scope_fields=("work_description",),
    point_fields=_GEO_POINT_FIELDS,
)


def _nyc_scope_builder(raw_item: dict) -> tuple:
    raw_scope = (
        f"Work on Floor: {raw_item.get('work_on_floor', 'N/A')}. "
        f"Job Description: {raw_item.get('job_description', 'N/A')}"
    )
    scope_summary = f"Permit issued for {raw_item.get('work_type', 'general')} construction."
    return raw_scope, scope_summary


NYC_MAPPING = FieldMapping(
    jurisdiction="nyc",
    source_url="https://a810-dobnow.nyc.gov/html/",
    permit_id_field="job_filing_number",
    address_fields=("house_no", "street_name"),
    date_fields=("issued_date", "approved_date"),
    owner_name_fields=("owner_name",),
    contractor_name_fields=("licensee_s_business_name",),
    permit_type_fields=("work_type", "filing_reason"),
    valuation_field="estimated_job_costs",
    scope_builder=_nyc_scope_builder,
    point_fields=_GEO_POINT_FIELDS,
)


AUSTIN_MAPPING = FieldMapping(
    jurisdiction="austin",
    source_url="https://data.austintexas.gov/resource/3syk-w9eu.json",
    permit_id_field="permit_number",
    address_fields=("original_address1",),
    date_fields=("issue_date",),
    contractor_name_fields=("contractor_company_name", "contractor_name"),
    permit_type_fields=("work_class", "permit_class_mapped"),
    square_footage_field="total_lot_sq_ft",
    valuation_field="total_job_valuation",
    scope_fields=("description", "project_name"),
    point_fields=_GEO_POINT_FIELDS,
)


SEATTLE_MAPPING = FieldMapping(
    jurisdiction="seattle",
    source_url="https://data.seattle.gov/resource/76t5-zqzr.json",
    permit_id_field="permitnum",
    address_fields=("originaladdress1", "originalcity", "originalstate", "originalzip"),
    address_separator=", ",
    date_fields=("issueddate", "applieddate"),
    permit_type_fields=("permittypedesc", "permitclass"),
    valuation_field="estprojectcost",
    scope_fields=("description",),
    point_fields=_GEO_POINT_FIELDS,
)


LA_MAPPING = FieldMapping(
    jurisdiction="la",
    source_url="https://data.lacity.org/resource/xnhu-aczu.json",
    permit_id_field="pcis_permit",
    address_fields=("address_start", "street_direction", "street_name", "street_suffix", "zip_code"),
    date_fields=("issue_date",),
    contractor_name_fields=("contractors_business_name",),
    permit_type_fields=("permit_type", "permit_sub_type"),
    valuation_field="valuation",
    square_footage_field="floor_area_l_a_building_code_definition",
    scope_fields=("work_description",),
)


DC_MAPPING = FieldMapping(
    jurisdiction="dc",
    source_url="https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17",
    permit_id_field="PERMIT_ID",
    address_fields=("FULL_ADDRESS",),
    date_fields=("ISSUE_DATE",),
    owner_name_fields=("OWNER_NAME",),
    contractor_name_fields=("PERMIT_APPLICANT",),
    permit_type_fields=("PERMIT_TYPE_NAME", "PERMIT_SUBTYPE_NAME", "PERMIT_CATEGORY_NAME"),
    scope_fields=("DESC_OF_WORK",),
)

SF_MAPPING = FieldMapping(
    jurisdiction='sf',
    source_url='https://data.sfgov.org/resource/i98e-djp9.json',
    permit_id_field='permit_number',
    address_fields=('street_number', 'street_number_suffix', 'street_name', 'street_suffix', 'unit', 'unit_suffix'),
    address_separator=' ',
    date_fields=('permit_creation_date', 'filed_date', 'issued_date', 'approved_date'),
    owner_name_fields=(),
    contractor_name_fields=(),
    permit_type_fields=('permit_type_definition', 'permit_type'),
    valuation_field='estimated_cost',
    square_footage_field=None,
    scope_fields=('description',),
    point_fields=('location',),
)


SAN_DIEGO_COUNTY_MAPPING = FieldMapping(
    jurisdiction='san_diego_county',
    source_url='https://data.sandiegocounty.gov/resource/dyzh-7eat.json',
    permit_id_field='record_id',
    address_fields=('full_address',),
    address_separator=' ',
    date_fields=('issued_date', 'open_date'),
    owner_name_fields=(),
    contractor_name_fields=('contractor_name',),
    permit_type_fields=('record_category', 'record_type', 'record_subtype', 'primary_scope_code'),
    valuation_field='valuation',
    square_footage_field='floor_area',
    scope_fields=('use',),
    point_fields=('geocoded_column',),
)


CAMBRIDGE_MAPPING = FieldMapping(
    jurisdiction='cambridge',
    source_url='https://data.cambridgema.gov/resource/9qm7-wbdc.json',
    permit_id_field='id',
    address_fields=('full_address',),
    address_separator=' ',
    date_fields=('issue_date', 'applicant_submit_date'),
    owner_name_fields=(),
    contractor_name_fields=('licensed_name', 'applicant_name'),
    permit_type_fields=('permit_type', 'construction_type', 'proposed_building_use', 'proposed_property_use'),
    valuation_field='total_cost_of_construction',
    square_footage_field='gross_square_footage',
    scope_fields=('description_of_work', 'isd_approved_description'),
    point_fields=('coordinates',),
)


SEATTLE_ALT_MAPPING = FieldMapping(
    jurisdiction='seattle',
    source_url='https://data.seattle.gov/resource/8tqq-u7ib.json',
    permit_id_field='permitnum',
    address_fields=('originaladdress1', 'originalcity', 'originalstate', 'originalzip'),
    address_separator=' ',
    date_fields=('issueddate', 'applieddate'),
    owner_name_fields=(),
    contractor_name_fields=('contractorcompanyname',),
    permit_type_fields=('permittypedesc', 'permitclass', 'permitclassmapped'),
    valuation_field='estprojectcost',
    square_footage_field=None,
    scope_fields=('description',),
    point_fields=('location1',),
)

NEW_ORLEANS_MAPPING = FieldMapping(
    jurisdiction='new_orleans',
    source_url='https://data.nola.gov/resource/nbcf-m6c2.json',
    permit_id_field='numstring',
    address_fields=('address',),
    address_separator=' ',
    date_fields=('issuedate',),
    owner_name_fields=(),
    contractor_name_fields=(),
    permit_type_fields=('permittype', 'proposeduseindustry', 'landuse', 'topcat', 'proposedusecategory'),
    valuation_field='constructionval',
    square_footage_field=None,
    scope_fields=('descr',),
    point_fields=('the_geom',),
)


CINCINNATI_MAPPING = FieldMapping(
    jurisdiction='cincinnati',
    source_url='https://data.cincinnati-oh.gov/resource/uhjb-xac9.json',
    permit_id_field='permitnum',
    address_fields=('originaladdress1', 'originalcity', 'originalstate', 'originalzip'),
    address_separator=', ',
    date_fields=('issueddate', 'applieddate'),
    owner_name_fields=(),
    contractor_name_fields=('companyname',),
    permit_type_fields=('permittypemapped', 'permittype', 'workclassmapped', 'workclass', 'permitclass'),
    valuation_field='estprojectcostdec',
    square_footage_field='totalsqft',
    scope_fields=('description', 'proposeduse'),
    point_fields=(),
)


VIRGINIA_BEACH_MAPPING = FieldMapping(
    jurisdiction='virginia_beach',
    source_url='https://services2.arcgis.com/CyVvlIiUfRBmMQuu/arcgis/rest/services/Building_Permits_Applications_view/FeatureServer/0',
    permit_id_field='PermitNumber',
    address_fields=('StreetAddress', 'AddressUnit', 'City', 'State', 'Zip'),
    address_separator=' ',
    date_fields=('IssueDate', 'ApplicationDate'),
    owner_name_fields=(),
    contractor_name_fields=(),
    permit_type_fields=('PermitType', 'ConstructionType', 'WorkType'),
    valuation_field=None,
    square_footage_field=None,
    scope_fields=('WorkDesc',),
    point_fields=(),
)


ALBUQUERQUE_MAPPING = FieldMapping(
    jurisdiction='albuquerque',
    source_url='https://coageo.cabq.gov/cabqgeo/rest/services/agis/City_Building_Permits/FeatureServer/0',
    permit_id_field='PermitNumber',
    address_fields=('CalculatedAddress',),
    address_separator=' ',
    date_fields=('DateIssued', 'DateEntered', 'created_date'),
    owner_name_fields=('Owner',),
    contractor_name_fields=('Contractor',),
    permit_type_fields=('TypeofWork', 'GeneralCategory', 'TypeofStructure'),
    valuation_field='Valuation',
    square_footage_field='SquareFootage',
    scope_fields=('WorkDescription',),
    point_fields=(),
)


BALTIMORE_MAPPING = FieldMapping(
    jurisdiction='baltimore',
    source_url='https://egisdata.baltimorecity.gov/egis/rest/services/Housing/DHCD_Open_Baltimore_Datasets/FeatureServer/3',
    permit_id_field='CaseNumber',
    address_fields=('Address',),
    address_separator=' ',
    date_fields=('IssuedDate',),
    owner_name_fields=(),
    contractor_name_fields=(),
    permit_type_fields=('PermitName', 'ExistingUse', 'ProposedUse'),
    valuation_field='Cost',
    square_footage_field=None,
    scope_fields=('Description',),
    point_fields=(),
)


KANSAS_CITY_MAPPING = FieldMapping(
    jurisdiction='kansas_city',
    source_url='https://data.kcmo.org/resource/w8jz-wjgn.json',
    permit_id_field='permit_number',
    address_fields=('main_address_line1', 'main_address_line2'),
    address_separator=', ',
    date_fields=('issue_date', 'application_date'),
    owner_name_fields=(),
    contractor_name_fields=(),
    permit_type_fields=('permit_type', 'work_class'),
    valuation_field='valuation',
    square_footage_field='square_feet',
    scope_fields=('project',),
    point_fields=(),
)


COLUMBUS_MAPPING = FieldMapping(
    jurisdiction='columbus',
    source_url='https://gis.columbus.gov/arcgis/rest/services/Applications/Neighborhood/MapServer/41',
    permit_id_field='B1_ALT_ID',
    address_fields=('SITE_ADDRESS', 'B1_SITUS_ZIP'),
    address_separator=' ',
    date_fields=(),
    owner_name_fields=(),
    contractor_name_fields=(),
    permit_type_fields=('CONST_TYPE_CODE',),
    valuation_field=None,
    square_footage_field=None,
    scope_fields=(),
    point_fields=(),
)


NEW_BERN_MAPPING = FieldMapping(
    jurisdiction='new_bern',
    source_url='https://gis.newbernnc.gov/arcgis/rest/services/Dev_Services/Building_Permits/FeatureServer/0',
    permit_id_field='PERMIT_NO',
    address_fields=('ADDRESS',),
    address_separator=' ',
    date_fields=('DATE_ISSUE',),
    owner_name_fields=('OWN_FIRST', 'OWNER_LAST'),
    contractor_name_fields=(),
    permit_type_fields=('TYPE2', 'TYPE'),
    valuation_field='EST_COST',
    square_footage_field=None,
    scope_fields=('DESCRIPT',),
    point_fields=(),
)


DENVER_MAPPING_COMMERCIAL = FieldMapping(
    jurisdiction='denver',
    source_url='https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_DEV_COMMERCIALCONSTPERMIT_P/FeatureServer/317',
    permit_id_field='PERMIT_NUM',
    address_fields=('ADDRESS',),
    address_separator=' ',
    date_fields=('DATE_ISSUED', 'DATE_RECEIVED'),
    owner_name_fields=(),
    contractor_name_fields=('CONTRACTOR_NAME',),
    permit_type_fields=('CLASS',),
    valuation_field='VALUATION',
    square_footage_field=None,
    scope_fields=('LOCATION',),
    point_fields=(),
)


DENVER_MAPPING_RESIDENTIAL = FieldMapping(
    jurisdiction='denver',
    source_url='https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_DEV_RESIDENTIALCONSTPERMIT_P/FeatureServer/316',
    permit_id_field='PERMIT_NUM',
    address_fields=('ADDRESS_NUMBER', 'ADDRESS_STREETDIR', 'ADDRESS_STREETNAME', 'ADDRESS_STREETTYPE', 'ADDRESS_UNITTYPE', 'ADDRESS_UNIT'),
    address_separator=' ',
    date_fields=('DATE_ISSUED', 'DATE_RECEIVED'),
    owner_name_fields=(),
    contractor_name_fields=('CONTRACTOR_NAME',),
    permit_type_fields=('CLASS',),
    valuation_field='VALUATION',
    square_footage_field=None,
    scope_fields=(),
    point_fields=(),
)


NASHVILLE_MAPPING = FieldMapping(
    jurisdiction='nashville',
    source_url='https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/Building_Permits_Issued_2/FeatureServer/0',
    permit_id_field='Permit__',
    address_fields=('Address', 'City', 'State', 'ZIP'),
    address_separator=' ',
    date_fields=('Date_Issued', 'Date_Entered'),
    owner_name_fields=(),
    contractor_name_fields=('Contact',),
    permit_type_fields=('Permit_Type_Description', 'Permit_Subtype_Description', 'Per_Ty', 'Per_SubTy'),
    valuation_field='Const_Cost',
    square_footage_field=None,
    scope_fields=('Purpose',),
    point_fields=(),
)


RALEIGH_MAPPING = FieldMapping(
    jurisdiction='raleigh',
    source_url='https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Building_Permits/FeatureServer/0',
    permit_id_field='permitnum',
    address_fields=('streetnum', 'streetdirectionprefix', 'streetname', 'streettype', 'streetdirectionsuffix'),
    address_separator=' ',
    date_fields=('issueddate', 'applieddate'),
    owner_name_fields=('parcelownername',),
    contractor_name_fields=('contractorcompanyname', 'contractordba'),
    permit_type_fields=('permittype', 'permittypemapped', 'workclass', 'workclassmapped', 'permitclass', 'permitclassmapped'),
    valuation_field='estprojectcost',
    square_footage_field='totalsqft',
    scope_fields=('proposedworkdescription', 'description', 'perm_comments', 'reviewercomments'),
    point_fields=(),
)


MIAMI_DADE_MAPPING = FieldMapping(
    jurisdiction='miami_dade',
    source_url='https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/miamidade_permit_data/FeatureServer/0',
    permit_id_field='PermitNumber',
    address_fields=('PropertyAddress',),
    address_separator=' ',
    date_fields=('PermitIssuedDate', 'ApplicationDate'),
    owner_name_fields=('OwnerName',),
    contractor_name_fields=('ContractorName',),
    permit_type_fields=('PermitType', 'ApplicationTypeDescription', 'ProposedUseDescription', 'CategoryDescription1'),
    valuation_field='EstimatedValue',
    square_footage_field='SquareFootage',
    scope_fields=('DetailDescriptionComments',),
    point_fields=(),
)


MINNEAPOLIS_MAPPING = FieldMapping(
    jurisdiction='minneapolis',
    source_url='https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services/CCS_Permits/FeatureServer/0',
    permit_id_field='permitNumber',
    address_fields=('Display',),
    address_separator=' ',
    date_fields=('issueDate',),
    owner_name_fields=('fullName',),
    contractor_name_fields=('applicantName',),
    permit_type_fields=('permitType', 'workType', 'occupancyType'),
    valuation_field='value',
    square_footage_field=None,
    scope_fields=('comments',),
    point_fields=(),
)


SIOUX_FALLS_MAPPING = FieldMapping(
    jurisdiction='sioux_falls',
    source_url='https://gis.siouxfalls.gov/arcgis/rest/services/Data/Community/MapServer/3',
    permit_id_field='PERMITNUMBER',
    address_fields=('MAINADDRESS',),
    address_separator=' ',
    date_fields=('ISSUEDATE', 'APPLYDATE'),
    owner_name_fields=(),
    contractor_name_fields=('contractor_name',),
    permit_type_fields=('PERMITTYPE', 'WORKCLASS'),
    valuation_field='VALUATION',
    square_footage_field=None,
    scope_fields=(),
    point_fields=(),
)


SOURCES = {
    "chicago": SocrataAPISource(
        name="chicago",
        url="https://data.cityofchicago.org/api/v3/views/ydr8-5enu/query.json",
        date_column="issue_date",
        mapper_func=build_mapper(CHICAGO_MAPPING),
    ),
    "nyc": SocrataAPISource(
        name="nyc",
        url="https://data.cityofnewyork.us/api/v3/views/rbx6-tga4/query.json",
        date_column="issued_date",
        mapper_func=build_mapper(NYC_MAPPING),
        skip_sentinel_field="permit_id",
        skip_sentinel_value="Permit is no",
    ),
    "austin": SocrataAPISource(
        name="austin",
        url="https://data.austintexas.gov/api/v3/views/3syk-w9eu/query.json",
        date_column="issue_date",
        mapper_func=build_mapper(AUSTIN_MAPPING),
    ),
    "seattle": SocrataAPISource(
        name="seattle",
        url="https://data.seattle.gov/api/v3/views/76t5-zqzr/query.json",
        date_column="issueddate",
        mapper_func=build_mapper(SEATTLE_MAPPING),
    ),
    "la": SocrataAPISource(
        name="la",
        url="https://data.lacity.org/api/v3/views/xnhu-aczu/query.json",
        date_column="issue_date",
        mapper_func=build_mapper(LA_MAPPING),
    ),
    "dc": ArcGISFeatureSource(
        name="dc",
        url="https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17",
        date_column="ISSUE_DATE",
        mapper_func=build_mapper(DC_MAPPING),
    ),
    "allen": PDFLedgerSource(
        name="allen",
        folder_path="./allen_pdfs",
        extraction_hints=(
            "You are an expert data extraction engine parsing a municipal ledger page.\n"
            "CRITICAL BLOCK-IDENTIFICATION RULES:\n"
            "1. Every distinct permit entry begins at the far left with a unique alpha-numeric Permit Number pattern "
            "(e.g., '000397-2026-CO', '000808-2026-CO*', '007623-2025-CB*').\n"
            "2. IGNORE the text color of the permit number—it may be RED or DARK BLUE depending on the work class category.\n"
            "3. Extract all permit classifications on the page, including 'Commercial Building - Alteration', "
            "'Certificate of Occupancy - C/O Stand Alone', 'Commercial Misc', etc.\n"
            "4. Disregard lines containing summary metrics or 'SUBTOTALS'."
        ),
    ),
    "naperville": PDFLedgerSource(
        name="naperville",
        folder_path="./naperville_pdfs"
    ),
    "sf": SocrataAPISource(
        name="sf",
        url="https://data.sfgov.org/api/v3/views/i98e-djp9/query.json",
        date_column="permit_creation_date",
        mapper_func=build_mapper(SF_MAPPING),
    ),
    "san_diego_county": SocrataAPISource(
        name="san_diego_county",
        url="https://data.sandiegocounty.gov/api/v3/views/dyzh-7eat/query.json",
        date_column="issued_date",
        mapper_func=build_mapper(SAN_DIEGO_COUNTY_MAPPING),
    ),
    "cambridge": SocrataAPISource(
        name="cambridge",
        url="https://data.cambridgema.gov/api/v3/views/9qm7-wbdc/query.json",
        date_column="issue_date",
        mapper_func=build_mapper(CAMBRIDGE_MAPPING),
    ),
    "seattle_alt": SocrataAPISource(
        name="seattle_alt",
        url="https://data.seattle.gov/api/v3/views/8tqq-u7ib/query.json",
        date_column="issueddate",
        mapper_func=build_mapper(SEATTLE_ALT_MAPPING),
    ),
    "new_orleans": SocrataAPISource(
        name="new_orleans",
        url="https://data.nola.gov/api/v3/views/nbcf-m6c2/query.json",
        date_column="issuedate",
        mapper_func=build_mapper(NEW_ORLEANS_MAPPING),
    ),
    "cincinnati": SocrataAPISource(
        name="cincinnati",
        url="https://data.cincinnati-oh.gov/api/v3/views/uhjb-xac9/query.json",
        date_column="issueddate",
        mapper_func=build_mapper(CINCINNATI_MAPPING),
    ),
    "virginia_beach": ArcGISFeatureSource(
        name="virginia_beach",
        url="https://services2.arcgis.com/CyVvlIiUfRBmMQuu/arcgis/rest/services/Building_Permits_Applications_view/FeatureServer/0",
        date_column="IssueDate",
        mapper_func=build_mapper(VIRGINIA_BEACH_MAPPING),
    ),
    "albuquerque": ArcGISFeatureSource(
        name="albuquerque",
        url="https://coageo.cabq.gov/cabqgeo/rest/services/agis/City_Building_Permits/FeatureServer/0",
        date_column="DateIssued",
        mapper_func=build_mapper(ALBUQUERQUE_MAPPING),
    ),
    "baltimore": ArcGISFeatureSource(
        name="baltimore",
        url="https://egisdata.baltimorecity.gov/egis/rest/services/Housing/DHCD_Open_Baltimore_Datasets/FeatureServer/3",
        date_column="IssuedDate",
        mapper_func=build_mapper(BALTIMORE_MAPPING),
    ),
    "kansas_city": SocrataAPISource(
        name="kansas_city",
        url="https://data.kcmo.org/api/v3/views/w8jz-wjgn/query.json",
        date_column="issue_date",
        mapper_func=build_mapper(KANSAS_CITY_MAPPING),
    ),
    "columbus": ArcGISFeatureSource(
        name="columbus",
        url="https://gis.columbus.gov/arcgis/rest/services/Applications/Neighborhood/MapServer/41",
        date_column="ISSUED_YEAR",
        mapper_func=build_mapper(COLUMBUS_MAPPING),
    ),
    "new_bern": ArcGISFeatureSource(
        name="new_bern",
        url="https://gis.newbernnc.gov/arcgis/rest/services/Dev_Services/Building_Permits/FeatureServer/0",
        date_column="DATE_ISSUE",
        mapper_func=build_mapper(NEW_BERN_MAPPING),
    ),
    "denver_commercial": ArcGISFeatureSource(
        name="denver_commercial",
        url="https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_DEV_COMMERCIALCONSTPERMIT_P/FeatureServer/317",
        date_column="DATE_ISSUED",
        mapper_func=build_mapper(DENVER_MAPPING_COMMERCIAL),
    ),
    "denver_residential": ArcGISFeatureSource(
            name="denver_residential",
            url="https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_DEV_RESIDENTIALCONSTPERMIT_P/FeatureServer/317",
            date_column="DATE_ISSUED",
            mapper_func=build_mapper(DENVER_MAPPING_RESIDENTIAL),
        ),
    "nashville": ArcGISFeatureSource(
        name="nashville",
        url="https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/Building_Permits_Issued_2/FeatureServer/0",
        date_column="Date_Issued",
        mapper_func=build_mapper(NASHVILLE_MAPPING),
    ),
    "raleigh": ArcGISFeatureSource(
        name="raleigh",
        url="https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Building_Permits/FeatureServer/0",
        date_column="issueddate",
        mapper_func=build_mapper(RALEIGH_MAPPING),
    ),
    "miami_dade": ArcGISFeatureSource(
        name="miami_dade",
        url="https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/miamidade_permit_data/FeatureServer/0",
        date_column="PermitIssuedDate",
        mapper_func=build_mapper(MIAMI_DADE_MAPPING),
    ),
    "minneapolis": ArcGISFeatureSource(
        name="minneapolis",
        url="https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services/CCS_Permits/FeatureServer/0",
        date_column="issueDate",
        mapper_func=build_mapper(MINNEAPOLIS_MAPPING),
    ),
    "sioux_falls": ArcGISFeatureSource(
        name="sioux_falls",
        url="https://gis.siouxfalls.gov/arcgis/rest/services/Data/Community/MapServer/3",
        date_column="ISSUEDATE",
        mapper_func=build_mapper(SIOUX_FALLS_MAPPING),
    ),
}


def get_source(name: str):
    try:
        return SOURCES[name.lower()]
    except KeyError:
        raise ValueError(
            f"Unknown jurisdiction '{name}'. Available: {', '.join(sorted(SOURCES))}"
        )


def list_sources() -> list[str]:
    return sorted(SOURCES.keys())
