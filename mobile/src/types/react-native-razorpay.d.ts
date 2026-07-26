/**
 * Type declarations for react-native-razorpay.
 * The package provides a native module that opens the Razorpay Checkout sheet.
 *
 * Full types: https://github.com/razorpay/react-native-razorpay
 * NOTE: After running `npm install` and `expo run:android`, the full
 *       @types/react-native-razorpay package can replace this stub.
 */
declare module 'react-native-razorpay' {
  export interface RazorpayCheckoutOptions {
    /** rzp_test_xxx — public test key (never the secret) */
    key: string;
    /** Razorpay order_id (order_xxx) */
    order_id: string;
    /** Amount in paise as a string, e.g. "50000" for ₹500 */
    amount: string;
    currency?: string;
    name?: string;
    description?: string;
    image?: string;
    prefill?: {
      name?: string;
      email?: string;
      contact?: string;
    };
    theme?: { color?: string };
    [key: string]: unknown;
  }

  export interface RazorpaySuccessResponse {
    razorpay_payment_id: string;
    razorpay_order_id: string;
    razorpay_signature: string;
  }

  export interface RazorpayErrorResponse {
    code: number;
    description: string;
  }

  const RazorpayCheckout: {
    open(options: RazorpayCheckoutOptions): Promise<RazorpaySuccessResponse>;
  };

  export default RazorpayCheckout;
}
