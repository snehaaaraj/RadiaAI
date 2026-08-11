declare module 'mammoth/mammoth.browser' {
  interface ExtractRawTextResult {
    value: string;
    messages: Array<{
      type: string;
      message: string;
    }>;
  }

  interface ExtractRawTextOptions {
    arrayBuffer: ArrayBuffer;
  }

  const mammoth: {
    extractRawText(options: ExtractRawTextOptions): Promise<ExtractRawTextResult>;
  };

  export default mammoth;
}
