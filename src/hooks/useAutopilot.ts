import { useCallback, useRef, useState } from "react";
import type { LoadedMessage } from "../protocol/types.js";

export interface UseAutopilotOptions {
  onPopulate: (text: string) => void;
}

export function useAutopilot({ onPopulate }: UseAutopilotOptions) {
  const [isActive, setIsActive] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [totalCount, setTotalCount] = useState(0);

  const queueRef = useRef<string[]>([]);
  const waitingForResponse = useRef(false);

  const initialize = useCallback(
    (messages: LoadedMessage[]) => {
      const userMessages = messages
        .filter((m) => m.role === "user" && m.content && m.content.trim() !== "")
        .map((m) => m.content.trim());

      if (userMessages.length === 0) {
        return;
      }

      queueRef.current = userMessages;
      setTotalCount(userMessages.length);
      setCurrentIndex(0);
      setIsActive(true);
      waitingForResponse.current = false;
      onPopulate(userMessages[0]);
    },
    [onPopulate],
  );

  const advance = useCallback((): boolean => {
    const queue = queueRef.current;
    const nextIdx = currentIndex + 1;

    if (nextIdx >= queue.length) {
      // Queue exhausted
      setIsActive(false);
      waitingForResponse.current = false;
      return false;
    }

    setCurrentIndex(nextIdx);
    onPopulate(queue[nextIdx]);
    return true;
  }, [currentIndex, onPopulate]);

  const markWaitingForResponse = useCallback(() => {
    waitingForResponse.current = true;
  }, []);

  const notifyStreamEnd = useCallback(() => {
    if (!waitingForResponse.current) return;
    waitingForResponse.current = false;
    advance();
  }, [advance]);

  const disable = useCallback(() => {
    setIsActive(false);
    waitingForResponse.current = false;
    onPopulate("");
  }, [onPopulate]);

  return {
    isActive,
    currentIndex,
    totalCount,
    initialize,
    advance,
    markWaitingForResponse,
    notifyStreamEnd,
    disable,
  };
}
