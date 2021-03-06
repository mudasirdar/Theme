{
    'name': 'JetMaster Website Customizations',
    'author': 'KPAK ',
    'version': '13.0.0.8',
    'summary': 'Jetmaster website customizations',
    'depends': ['website_sale', 'product', 'website_blog', 'sale_management'],
    'description': '',
    'data': [
        'security/ir.model.access.csv',
        'views/website_templates/contact_us_view.xml',
        'views/website_templates/gallery_view.xml',
        'views/website_templates/homepage.xml',
        'data/website_menus.xml',
        'views/templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
