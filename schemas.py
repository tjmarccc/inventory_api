from marshmallow import Schema, fields, validate


class UserSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=4, max=128))


class ProductSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    description = fields.Str(load_default=None, allow_none=True)
    price = fields.Float(required=True, validate=validate.Range(min=0))
    quantity = fields.Int(required=True, validate=validate.Range(min=0))
    category = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=50))
    user_id = fields.Int(dump_only=True)