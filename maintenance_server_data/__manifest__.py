# Copyright 2023 Stéphan Sainléger (Elabore)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "maintenance_server_data",
    "version": "14.0.1.0.0",
    "author": "Elabore",
    "website": "https://elabore.coop",
    "maintainer": "Stéphan Sainléger",
    "license": "AGPL-3",
    "category": "Tools",
    "summary": "Gather data about the servers to maintain.",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "maintenance",
    ],
    "qweb": [
        # "static/src/xml/*.xml",
    ],
    "external_dependencies": {
        "python": [],
    },
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/maintenance_equipment.xml",
        "views/os_distribution.xml",
        "views/service.xml",
    ],
    # only loaded in demonstration mode
    "demo": [],
    "js": [],
    "css": [],
    "installable": True,
    # Install this module automatically if all dependency have been previously
    # and independently installed.  Used for synergetic or glue modules.
    "auto_install": False,
    "application": False,
}