# -*- coding: utf-8 -*-
{
    "name": "Estate Rent Management",
    "summary": "Buildings, units, rent contracts, and GL tagging (Odoo 18)",
    "version": "18.0.1.0.0",
    "author": "Mustafa Thaeer",
    "website": "https://github.com/mustafa327",
    "support": "mustafathaear97@gmail.com",
    "license": "LGPL-3",
    "category": "Accounting/Real Estate",

    "depends": [
        "base",
        "contacts",
        "hr",
        "sale",
        "account",
    ],

    "data": [
        "security/ir.model.access.csv",
        
        "views/estate_building_views.xml",
        "views/estate_unit_views.xml",
        "views/rent_contract_views.xml",
        "views/inherit_partner_views.xml",
        "views/inherit_sale_order_views.xml",
        "views/inherit_account_move_views.xml",
        "views/estate_menus.xml",
        "views/rent_prepayment_view.xml",
        "views/utility_views.xml",
        "data/rent_cron.xml",
    ],
    
    "installable": True,
    "application": True,
}