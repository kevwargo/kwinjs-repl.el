;;; kwinjs-repl --- REPL for talking to KWin JS engine  -*- lexical-binding: t -*-

;; Author: kevwargo
;; Package-Requires: ((emacs "30.1"))

;;; Commentary:

;;; Code:

(require 'comint)

(defvar kwinjs--repl nil)
(if (and load-file-name (null kwinjs--repl))
    (setq kwinjs--repl
          (expand-file-name
           "kwinjs-repl.py"
           (file-name-directory (file-truename (file-name-with-extension
                                                (file-name-sans-extension load-file-name)
                                               "el"))))))

(define-derived-mode kwinjs-mode comint-mode "KWINJS"
  (unless (comint-check-proc (current-buffer))
    (setq-local comint-prompt-regexp "^KWin JS #> ")
    (setq-local comint-use-prompt-regexp t)
    (setq-local comint-prompt-read-only t)

    (setq-local comint-input-sender
                (lambda (proc string)
                  (comint-send-string proc (concat (json-serialize string) "\n"))))

    (kwinjs-init-process)
    (goto-char (point-max))))

;;;###autoload
(defun kwinjs ()
  (interactive)
  (let* ((bufname "*kwinjs*")
         (buf (get-buffer bufname)))
    (unless buf
      (with-current-buffer (setq buf (get-buffer-create bufname))
        (kwinjs-mode)))
    (pop-to-buffer buf)))

(defun kwinjs-send ()
  (interactive)
  (if (eq (char-before (point)) ?\;)
      (comint-send-input)
    (newline)))

(defun kwinjs-init-process ()
  (interactive)
  (make-comint-in-buffer "kwinjs"
                         (current-buffer)
                         kwinjs--repl))

(defun kwinjs-eof ()
  (interactive)
  (process-send-eof))

(keymap-set kwinjs-mode-map "RET" 'kwinjs-send)
(keymap-set kwinjs-mode-map "C-c RET" 'kwinjs-init-process)
(keymap-set kwinjs-mode-map "C-c C-<return>" 'kwinjs-init-process)
(keymap-set kwinjs-mode-map "C-d" 'kwinjs-eof)

(provide 'kwinjs)
