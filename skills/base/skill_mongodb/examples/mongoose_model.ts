// Mongoose schema + model — TypeScript production pattern
import mongoose, { Document, Model, Schema } from 'mongoose';

export interface IUser extends Document {
  email:     string;
  fullName:  string;
  password:  string;
  role:      'user' | 'admin';
  isActive:  boolean;
  createdAt: Date;
}

const UserSchema = new Schema<IUser>({
  email:    { type: String, required: true, unique: true, lowercase: true, trim: true, index: true },
  fullName: { type: String, required: true, trim: true },
  password: { type: String, required: true, select: false },  // never returned by default
  role:     { type: String, enum: ['user', 'admin'], default: 'user' },
  isActive: { type: Boolean, default: true },
}, { timestamps: true });

// Never expose password in JSON responses
UserSchema.methods.toJSON = function () {
  const obj = this.toObject();
  delete obj.password;
  return obj;
};

export const UserModel: Model<IUser> = mongoose.model<IUser>('User', UserSchema);
