from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class EstateBuildingUnit(models.Model):
    _name = 'estate.building.unit'
    _description = 'Building Unit (Apartment)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='اسم الشقة/الوحدة', required=True, tracking=True)
    building_id = fields.Many2one('estate.building', string='البناية', required=True, ondelete='cascade', tracking=True)
    owner_id = fields.Many2one('res.partner', string="Owner (Unit) / مالك الوحدة", domain=[('is_property_owner', '=', True)], help="If empty, we fallback to the building owner.")
    floor = fields.Integer(string='رقم الطابق', tracking=True)
    unit_number = fields.Char(string='رقم الشقة', tracking=True)

    department_id = fields.Many2one('hr.department', string='القسم (اختياري)')

    tenant_id = fields.Many2one('res.partner', string='المستأجر الحالي')
    contract_ids = fields.One2many('rent.contract', 'unit_id', string='عقود الإيجار')

    active_contract_id = fields.Many2one('rent.contract', string='العقد الفعّال', compute='_compute_active_contract', store=False)
    occupied = fields.Boolean(string='مشغولة؟', compute='_compute_active_contract', store=False)

    contract_count = fields.Integer(string='Contracts', compute='_compute_contract_count', store=False)

    @api.depends('contract_ids.state', 'contract_ids.start_date', 'contract_ids.end_date')
    def _compute_active_contract(self):
        today = fields.Date.context_today(self)
        for u in self:
            active = u.contract_ids.filtered(lambda c: c.state == 'active' and (not c.end_date or c.end_date >= today) and (not c.start_date or c.start_date <= today))
            u.active_contract_id = active[:1].id if active else False
            u.occupied = bool(active)

    @api.depends('owner_id', 'building_id.owner_id')
    def _compute_effective_owner_id(self):
        for rec in self:
            rec.effective_owner_id = rec.owner_id or rec.building_id.owner_id

    effective_owner_id = fields.Many2one(
        'res.partner', compute=_compute_effective_owner_id, store=True,
        string="Effective Owner / المالك الفعلي"
    )

    def action_new_contract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Contract'),
            'res_model': 'rent.contract',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_unit_id': self.id,
                'default_building_id': self.building_id.id,
                'default_partner_id': self.tenant_id.id or False,
                'default_company_id': (self.building_id.company_id.id or self.env.company.id),
            },
        }

    def _compute_contract_count(self):
        for u in self:
            u.contract_count = len(u.contract_ids)

    def action_open_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contracts'),
            'res_model': 'rent.contract',
            'view_mode': 'list,form',
            'domain': [('unit_id', '=', self.id)],
            'target': 'current',
        }

    def action_open_active_contract(self):
        self.ensure_one()
        if self.active_contract_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Active Contract'),
                'res_model': 'rent.contract',
                'view_mode': 'form',
                'res_id': self.active_contract_id.id,
                'target': 'current',
            }
        return self.action_open_contracts()