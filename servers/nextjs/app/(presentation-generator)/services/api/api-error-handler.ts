import {
  isChatGptAuthRequiredResponse,
  normalizeChatGptAuthMessage,
  requestChatGptReauth,
} from "@/utils/chatgptAuth";
import {
  extractApiErrorMessage,
  type ApiErrorResponse,
} from "@/utils/apiErrorMessages";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly retryable: boolean;
  readonly traceId: string | null;

  constructor(message: string, response: Response) {
    super(message);
    this.name = "ApiRequestError";
    this.status = response.status;
    this.retryable = response.status === 429 || response.status >= 500;
    this.traceId =
      response.headers.get("x-request-id") || response.headers.get("x-trace-id");
  }
}

// API Response Handler Utility
export class ApiResponseHandler {
  static async handleResponse(response: Response, defaultErrorMessage: string): Promise<any> {
    // Handle successful responses
    if (response.ok) {
      // Handle 204 No Content responses
      if (response.status === 204) {
        return true;
      }
      
      // Try to parse JSON response
      try {
        return await response.json();
      } catch {
        // If JSON parsing fails but response is ok, return empty object
        return {};
      }
    }

    // Handle error responses
    let errorMessage = defaultErrorMessage;
    
    try {
      const errorData: ApiErrorResponse = await response.json();
      errorMessage = extractApiErrorMessage(
        errorData,
        defaultErrorMessage,
        response.status
      );

      if (isChatGptAuthRequiredResponse(response, errorData, errorMessage)) {
        errorMessage = normalizeChatGptAuthMessage(errorMessage);
        requestChatGptReauth({
          message: errorMessage,
          source: "api-response",
        });
      }
    } catch {
      // If JSON parsing fails, use status-based messages
      errorMessage = this.getStatusBasedErrorMessage(response.status, defaultErrorMessage);
      if (isChatGptAuthRequiredResponse(response, null, errorMessage)) {
        errorMessage = normalizeChatGptAuthMessage(errorMessage);
        requestChatGptReauth({
          message: errorMessage,
          source: "api-response",
        });
      }
    }

    // Throw error with appropriate message
    throw new ApiRequestError(errorMessage, response);
  }


  static async handleResponseWithResult(response: Response, defaultErrorMessage: string): Promise<{success: boolean, message?: string}> {
    try {
      // Handle successful responses
      if (response.ok) {
        return { success: true };
      }

      // Handle error responses
      let errorMessage = defaultErrorMessage;
      
      try {
        const errorData: ApiErrorResponse = await response.json();
        errorMessage = extractApiErrorMessage(
          errorData,
          defaultErrorMessage,
          response.status
        );

        if (isChatGptAuthRequiredResponse(response, errorData, errorMessage)) {
          errorMessage = normalizeChatGptAuthMessage(errorMessage);
          requestChatGptReauth({
            message: errorMessage,
            source: "api-response-result",
          });
        }
      } catch {
        // If JSON parsing fails, use status-based messages
        errorMessage = this.getStatusBasedErrorMessage(response.status, defaultErrorMessage);
        if (isChatGptAuthRequiredResponse(response, null, errorMessage)) {
          errorMessage = normalizeChatGptAuthMessage(errorMessage);
          requestChatGptReauth({
            message: errorMessage,
            source: "api-response-result",
          });
        }
      }

      return {
        success: false,
        message: errorMessage,
      };
    } catch (error) {
      return {
        success: false,
        message: error instanceof Error ? error.message : defaultErrorMessage,
      };
    }
  }


  private static getStatusBasedErrorMessage(status: number, defaultMessage: string): string {
    switch (status) {
      case 400:
        return "请求内容不正确，请检查后重试。";
      case 401:
        return "登录状态已失效，请重新登录。";
      case 403:
        return "当前账号没有权限执行此操作。";
      case 404:
        return "未找到请求的内容，它可能已被删除或移动。";
      case 409:
        return "当前内容已发生变化，请刷新后重试。";
      case 422:
        return "部分信息不符合要求，请检查后重试。";
      case 429:
        return "操作过于频繁，请稍后重试。";
      case 500:
        return "服务处理失败，请稍后重试。";
      case 502:
        return "上游服务暂不可用，请稍后重试。";
      case 503:
        return "服务正在恢复中，请稍后重试。";
      case 504:
        return "任务处理超时，请稍后重试。";
      default:
        return defaultMessage;
    }
  }
}

export type { ApiErrorResponse };
